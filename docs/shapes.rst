Names the parser reads
======================

The input forms the parser reads without configuration: how a name is arranged, the words that attach to their neighbors, nicknames and maiden names, and titles it was not told about.


Input shapes
-------------

Three arrangements are understood by default, two more when you
declare a family-first order, and two more by how they are written.

Understood by default
~~~~~~~~~~~~~~~~~~~~~

Every piece of each is optional:

1. ``Title Given "Nickname" Middle Middle Family Suffix``
2. ``[Title] Family [Suffix], Title Given (Nickname) Middle Middle[,] Suffix [, Suffix or Title]``
3. ``Title Given Middle Family [Suffix], Suffix or Title [, Suffix or Title]``

A title written with a period (``Prof.``) is also read at the end of a
name in forms 1 and 3 and at the end of the given name in form 2;
written bare there (``Prof``), it is a name word, because many title
words are also surnames — unless a credential stands before it, which
starts a run of post-nominals and titles (``John Smith PhD Prof`` reads
title ``Prof``; see :ref:`trailing-titles`), or, at the end of the
given name in form 2, it is a listed salutation such as ``Mrs``
(``Doe, Jane Mrs`` reads title ``Mrs`` since 2.6;
``Lexicon.default().words(kind="salutation", after_given=True)`` lists
them).

The last two differ in what the comma is doing. In form 2 it separates
the family name from the rest, so the family name comes first; in form
3 it only sets off suffixes and titles, and the name before it is still
given-then-family:

.. doctest::

    >>> from nameparser import parse
    >>> parse("de la Vega, Juan Q. Xavier III").family   # form 2
    'de la Vega'
    >>> parse("Doe Jr., John").suffix                    # form 2, suffix before the comma
    'Jr.'
    >>> parse("John Doe, Jr.").family                    # form 3
    'Doe'

A suffix ending a name of two or more words (a title counts) before the comma reads as
form 3 even when what follows is a credential the vocabulary does not
know, since a generation is written there in natural order. A word
after the comma written as a name, or an initial, keeps form 2 (since
2.5):

.. doctest::

    >>> parse("John Smith II, AD").suffix
    'II, AD'
    >>> parse("Garcia Lopez Jr., Juan").given
    'Juan'

A part after the comma in form 3, or after a further comma in either
form, holds suffixes and titles, a word there that is a title rather
than a suffix being read as the title (after a further comma, since
2.4):

.. doctest::

    >>> parse("Eric H. Holder, Attorney General").title
    'Attorney General'
    >>> parse("Eric H. Holder, Jr., Attorney General").title
    'Attorney General'

Family-first forms you declare
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two more arrangements apply only when ``name_order`` declares
family-first input — common outside Europe; see :ref:`name-order`:

4. ``Title Family Given Middle Middle [Particle] [, Suffix]``  (``FAMILY_FIRST``)
5. ``Title Family Middle Middle Given [, Suffix]``  (``FAMILY_FIRST_GIVEN_LAST``)

A trailing particle earns a slot in form 4 alone because it is
displaced from the family name it belongs to; form 5's trailing word
is the given name by the caller's declaration, so there is nothing
there to reinterpret.

A title is read at the front of forms 4 and 5, which is where
family-first names written with a title put it. At the end of the name
it is read as in form 1: with a period it is the title, and bare it is a
name word unless a credential stands before it. Written between the
family and the given name, it is a name word, read by its position:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Parser, Policy
    >>> ff = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> ff.parse("Dr. Wang Xiaoming").title, ff.parse("Wang Xiaoming Dr.").title
    ('Dr.', 'Dr.')
    >>> ff.parse("Wang Dr. Xiaoming").given
    'Dr.'

Forms the script carries
~~~~~~~~~~~~~~~~~~~~~~~~

Two more arrangements are native East Asian forms. The first needs
no ``name_order`` at all — the script itself carries the reading —
and the second is read the way the default order reads it, its own
written order:

6. ``Family Given [Honorific]``
7. ``Given[·Given]·Family / katakana transcription (source order)``

Form 6 is the native family-first arrangement written in Han or
Hangul — spaced or unspaced, with the honorific spaced or glued and
landing in ``suffix``. It has no title slot and no comma, because
native CJK writing has neither convention. Form 7 is a transcription
listing — Han divided by the 间隔号, or katakana joined by the
nakaguro — never segmented, and kept in the order it was written as
long as ``name_order`` is the default: the script settles no order for
a transcription, so a declared ``FAMILY_FIRST`` reverses it as it
reverses a Latin name.

A comma or a Latin wrapper around a CJK name — a listing comma, a
Latin honorific or credential set beside it — is tolerated input:
parsed best-effort, its handling changeable without notice.

Forms 6 and 7, and how a Latin wrapper around either is handled, are
covered in full under :ref:`East Asian names <east-asian-names>` below.

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
reach forward to pull in the next word, whatever it is. Each row's
reading kind is what :meth:`Lexicon.words(kind=...)
<nameparser.Lexicon.words>` takes to list its words:

.. list-table::
   :header-rows: 1
   :widths: 22 26 12 40

   * - Words
     - Attach to
     - Field
     - Example
   * - Titles (``title``)
     - adjacent titles; a title that is also a given name, only inside
       a title phrase (:ref:`titles-also-given-names`)
     - ``title``
     - ``Asst. Vice Chancellor John`` → ``Asst. Vice Chancellor``
   * - Suffixes (``suffix``)
     - adjacent suffixes
     - ``suffix``
     - ``John Smith PhD MD`` → ``PhD MD``
   * - Bound given names (``bound_given``)
     - the following word
     - ``given``
     - ``abdul salam ahmed`` → ``abdul salam``
   * - Particles (``particle``)
     - the following surname, save a given name's second half
       (``del Carmen``), which is ``middle``
     - ``family``
     - ``Juan de la Vega`` → ``de la Vega``
   * - Ranks (``rank``)
     - the following surname, inside the name; opening it, most are
       titles (below)
     - ``family``
     - ``Jan Freiherr von Berg`` → ``Freiherr von Berg``
   * - Maiden markers (``birth_marker``)
     - the following name
     - ``maiden``
     - ``Jane Smith née Jones`` → ``Jones``
   * - Conjunctions (``conjunction``)
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

Most ranks (``Freiherr``, ``Graf``, ``Prinz``) are titles as well as
particles, and read by where they stand: opening the name each is a
title, and inside it the surname takes it in. ``Freiherrin`` holds no
title reading, so opening a name it is a name word. ``St`` reads the same
way, a title and a ``saint`` particle; the other ``saint`` words
(``San``, ``Sta``, ...) hold no title reading, so opening a name none
of them is a title:

.. doctest::

    >>> parse("Freiherr Hans von Berg").title
    'Freiherr'
    >>> parse("Jan Freiherr von Berg").family
    'Freiherr von Berg'
    >>> parse("St John Smith").title, parse("John St Clair").family
    ('St', 'St Clair')

Two shipped vocabularies work the other way round and so are not in
the table above: they *split* a word instead of merging two. The
Korean surnames (``Lexicon.default().surnames``) divide an unspaced
hangul name, and the glued honorifics, the ``honorific`` readings
carrying ``attached`` (``Lexicon.default().words(kind="honorific",
attached="after")`` lists them), split off the end of a Chinese,
Japanese or Korean name. Both are covered under :ref:`East Asian names <east-asian-names>`.
:doc:`customize` covers how to add and remove the readings behind each
of these rows.

Inspecting the vocabulary
~~~~~~~~~~~~~~~~~~~~~~~~~

Two questions explain why a word read as it did, and each has its own
call. What a word *may* be read as is the lexicon's answer,
:meth:`Lexicon.readings_of <nameparser.Lexicon.readings_of>`, each
reading naming the language files that hold it. What the parse *did*
read it as is the token's, :attr:`Token.reading
<nameparser.Token.reading>` (see :ref:`reading-taken`):

.. doctest::

    >>> from nameparser import Lexicon
    >>> [(r.kind, r.languages) for r in Lexicon.default().readings_of("van")]
    [('preposition', ('nl',)), ('given', ('nl',)), ('familiar', ('en',))]
    >>> parse("Ludwig van Beethoven").tokens[1].reading
    Reading('particle' as 'family', 'vocabulary', in nl)

A lexicon answers for the readings it has on. A reading its file holds
off until a caller chooses the language (:ref:`choosing-languages`) is not among
the default lexicon's: ``Lady`` is a given name only under a Spanish
choice, and only that parser's lexicon lists the reading:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> [r.kind for r in Lexicon.default().readings_of("lady")]
    ['nobility']
    >>> [r.kind for r in parser_for(locales.ES).lexicon.readings_of("lady")]
    ['nobility', 'given']

A particle at the start of a name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Position matters in exactly one place: a particle standing on its own
at the start of a name. It has no surname to attach to yet, so what
decides the reading is whether it is one that can double as a given
name: the particle either becomes the given name or turns the whole
name into a surname. Only the first of those is ``name_order``'s
question — see :ref:`order-vocabulary-first`, and read the given name
below as the default given-first order's — since a particle that can
never be a given name is the surname whatever order you declare:

.. doctest::

    >>> parse("van Gogh").given          # 'van' can be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' cannot
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

A comma gets there first. It names the surname outright, so a particle
opening that surname has nothing left to decide and the part after the
comma is the given name:

.. doctest::

    >>> parse("de Mesnil, Juan").given
    'Juan'

:ref:`ambiguous-words` covers changing which particles may double as
given names.

.. _nicknames-and-maiden-names:

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

Surviving a reparse
~~~~~~~~~~~~~~~~~~~

The default ``str()`` rendering is built for display, and the two
fields differ in what
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

What bracketed content reads as
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Delimited content is not always a nickname. If it opens with a marker
word and has a word after it, the clause is a maiden name inside any
configured delimiter pair, with nothing else configured — the clause
has said which convention it means, so you do not have to:

.. doctest::

    >>> parse("Jane Smith (née Jones)").maiden
    'Jones'
    >>> parse('Jane Smith "née Jones"').maiden
    'Jones'
    >>> parse("Jane (née Jones) Smith").family
    'Smith'

A marker with no name after it is just a word in brackets, and a clause
with no marker at all stays a nickname — the parenthesized birth surname
is a real convention, but nothing in the clause says so, and only you
can declare that with ``maiden_delimiters`` (see :ref:`brackets`):

.. doctest::

    >>> parse("Jane Smith (née)").nickname
    'née'
    >>> parse("Cherice J. (Johnson) Williams").nickname
    'Johnson'

If every word inside is a known
credential, generation or title, the clause is set apart from the name
instead, each word read as the suffix or the title it is — that reading
is taken before the maiden one, and parenthesized credentials, titles
and retired ranks are far more common than parenthesized nicknames that
happen to be credentials. Initials inside a name stay the nickname
(``Justin (JP) Stearns``), and other content ending in a period is read
as if written without its brackets:

.. doctest::

    >>> parse("Andrew Perkins (PhD)").suffix
    'PhD'
    >>> parse("Andrew Perkins (Ret.)").suffix
    'Ret.'
    >>> parse("John Smith (Dr)").title
    'Dr'

The exception to that exception is an *ambiguous* acronym — one that is
also a plausible name or set of initials. Standing alone inside
delimiters, it keeps the nickname reading unless the way it is written
settles it after the name: in capitals in a name written in mixed case,
or with a period inside it. A name written all in capitals says
nothing about the word, and inside the name the delimiters are read as
a nickname however it is written:

.. doctest::

    >>> parse("Andrew Perkins (JD)").suffix
    'JD'
    >>> parse("Andrew Perkins (Jd)").nickname
    'Jd'
    >>> parse("JEFFREY (JD) BRICKEN").nickname
    'JD'

``JD`` holds a ``given`` reading beside its credential one
(``Lexicon.default().readings_of("jd")``); see :ref:`ambiguous-words`
for what that second reading marks and how to add one.
:ref:`brackets` covers the full order these readings are tried in, and
how to configure the delimiter pairs.

.. _abbreviated-titles:

Titles you didn't configure
-----------------------------

A trailing period marks an abbreviation, and the parts of a name that
get abbreviated are mostly the ones standing outside it — titles and
post-nominals; the exception, a given name written short, is below. So a word ending in a period, in no vocabulary list at
all, is read as a title when it stands where a title stands: at the
front of the part that carries the given name. That is what lets
unfamiliar ranks, honorifics and abbreviations work without configuring
anything:

.. doctest::

    >>> parse("Insp. Jane Morse").title
    'Insp.'
    >>> parse("Det. Insp. Jane Morse").title     # chains
    'Det. Insp.'

Neither ``det`` nor ``insp`` is in the shipped vocabulary; the periods
are doing all the work.

The part that carries the given name is not always the front of the
string. After a family comma it is the part *after* the comma, and the
rule applies there in exactly the same way:

.. doctest::

    >>> parse("Morse, Det. Insp. Jane").title
    'Det. Insp.'

Where the inference stops
~~~~~~~~~~~~~~~~~~~~~~~~~

The rule is bounded so it doesn't swallow ordinary names:

- **Single initials** are left alone (``J.``).
- **Abbreviations with interior periods** are left alone (``E.T.``).
- **Only the leading run** is read this way: the same word after the
  given name is a middle name.
- **A word carrying a Han, kana or hangul character** is a name word
  even with a period,
  since those scripts write no abbreviation with one (``"田中. 太郎"``
  has family ``田中.``).
- **A word in one of the ten Brahmic scripts from Devanagari to Sinhala**
  (Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada,
  Malayalam, Sinhala) is a name word even with a period, since writers in
  them spell a Latin initial out by its sound
  (``"एम. एस. वर्मा"`` has given ``एम.``, middle ``एस.``). A listed title
  there (``डा.``) is still a title.
- **Before a family comma** the inference does not run, since that
  slot holds a surname too: ``Xyz. Smith, John`` keeps family
  ``Xyz. Smith``. A listed title is still read there, so
  ``Dr. Smith, John`` gives title ``Dr.``.
- **A given name written short** is that given name (since 2.7): the
  traditional English abbreviations such as ``Chas.``, ``Geo.`` and
  ``Wm.``, and the Filipino ``Ma.`` (María) and ``Jo.`` (José).
  Each is a ``given`` reading carrying ``same_as``, the full name
  (``Lexicon.default().readings_of("chas")``); written bare, or
  anywhere else in the name, each word reads as it would unlisted.

.. doctest::

    >>> parse("Chas. Smith").given
    'Chas.'
    >>> parse("Mrs Ma. Liza Cruz").given
    'Ma.'
    >>> parse("J. Smith").given
    'J.'
    >>> parse("E.T. Jones").given_names
    'E.T.'
    >>> parse("Jane Insp. Morse").middle
    'Insp.'
    >>> parse("Xyz. Smith, John").family
    'Xyz. Smith'

Because this is structural rather than vocabulary-driven, taking out
every title reading does not switch it off; see :ref:`title-detection-off`.

.. _trailing-titles:

At the end of a name
~~~~~~~~~~~~~~~~~~~~

Only the leading slot INFERS. At the back of a name a word ending in a
single period is read by vocabulary alone: a word the parser already
knows as a post-nominal or as a title reads as one, and an unfamiliar
abbreviation stays a name word. A word of two or more period-separated
chunks is the exception, read as a credential by its shape (see
:ref:`dotted-credentials`).

.. doctest::

    >>> parse("John Smith Prof.").title
    'Prof.'
    >>> parse("John Smith Xyz.").family
    'Xyz.'
    >>> parse("Jane Smith N.C.C.").suffix
    'N.C.C.'

That asymmetry is deliberate. The title vocabulary holds hundreds of
words that are ordinary surnames — ``pope``, ``judge``, ``bishop`` —
so inferring a trailing title from the shape alone would cost real
names their family field. The period is what separates the two: a
trailing title word written *without* one is a name word, so
``parse("Mary Jane Pope").family`` is ``'Pope'``.

A credential in front changes that. It starts a run of post-nominals
and titles that lasts to the end of the name, so a bare title word
behind it is a title:

.. doctest::

    >>> john_prof = parse("John Smith PhD Prof")
    >>> (john_prof.title, john_prof.suffix)
    ('Prof', 'PhD')
