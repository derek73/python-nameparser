Customizing the parser
=======================

Every piece of nameparser configuration sorts into one of three places
by asking what it varies with: vocabulary varies by **language**
(:class:`~nameparser.Lexicon`), behavior varies by **data source or
application** (:class:`~nameparser.Policy`), and presentation varies by
**output destination** (a rendering argument). See :doc:`concepts` for
why the split is drawn there.

Vocabulary: Lexicon
--------------------

When your data is in a known language, choosing it is the first thing
to try, before editing words one at a time. A choice of languages
(:ref:`choosing-languages`) makes the chosen language's reading win on
a word it lists as vocabulary, switching off another language's
(Portuguese ``do`` the particle over English ``DO`` the credential),
and turns on the readings its file holds off by default; a strict
choice (:ref:`strict-choice`) also drops the readings other languages'
files hold of words written in Latin letters, name readings included,
keeping the readings of the shared ``mul`` file. The edits below are for what a choice
leaves open, and for data whose language you cannot declare, which the
default vocabulary, reading every language at once, already serves.

Configuring by reading
~~~~~~~~~~~~~~~~~~~~~~~

A :class:`~nameparser.Lexicon` holds **readings**: what each word may be
read as, in the terms the shipped vocabulary files use. Configure it by
adding and removing readings:

.. doctest::

    >>> from nameparser import Lexicon, Parser, parse
    >>> parse("Dean Robert Johns").given
    'Dean'
    >>> [r.kind for r in Lexicon.default().readings_of("dean")]
    ['office', 'given', 'family']
    >>> lex = Lexicon.default().remove("dean", kind="given")
    >>> Parser(lexicon=lex).parse("Dean Robert Johns").title
    'Dean'

``dean`` holds a title reading (its kind is ``office``) and a ``given``
reading, and a title that may be a given name is a title only inside a
title phrase such as ``Dean of Students``
(:ref:`titles-also-given-names`). Removing the ``given`` reading makes
it a title wherever it stands. Adding a title reading instead would
change nothing outside a phrase, so ``add("dean", kind="title")`` warns
and names the ``remove`` above.

:meth:`~nameparser.Lexicon.add` takes the words and a ``kind``, and
:meth:`~nameparser.Lexicon.remove` the words and, optionally, a kind;
both return a new :class:`~nameparser.Lexicon`, the one you started
from (here, ``Lexicon.default()``) never being mutated. Where a word
holds a reading of the kind added, ``add`` updates that reading in every
file holding it; otherwise it adds a reading of the caller's own.
``remove`` with no kind takes out every reading of the word, with a
category (``"title"``, ``"name"``) every reading of that category, and
with a kind and ``every=True`` every word's readings of that kind.
:meth:`~nameparser.Lexicon.readings_of` answers what a word may be read
as here, each :class:`~nameparser.LexiconReading` naming the shipped
files that hold it, and :meth:`~nameparser.Lexicon.words` lists the
words holding a reading of a kind; whether a parse *read* a word that
way is :attr:`Token.reading <nameparser.Token.reading>`'s question.

A credential the defaults do not list is one reading per word:

.. doctest::

    >>> parse("John Smith LEED AP").suffix
    ''
    >>> lex = Lexicon.default().add("leed", "ap", kind="credential")
    >>> Parser(lexicon=lex).parse("John Smith LEED AP").suffix
    'LEED AP'

Removing works the same way, and a category takes out every reading of
it:

.. doctest::

    >>> lean = Lexicon.default().remove("professor", kind="title")
    >>> Parser(lexicon=lean).parse("Professor Robert Johns").title
    ''

The 2.x set fields (``titles``, ``suffix_acronyms``,
``particles_ambiguous``, ...) are internal since 3.0, compiled from the
readings: ``add(titles=...)``, ``Lexicon(titles=...)`` and
``lexicon.titles`` each raise, the error naming the calls that configure
the same words, and :doc:`migrate` has the table.

The default word lists are asked of a lexicon too:
:meth:`~nameparser.Lexicon.words` lists the words holding a reading of a
kind, as the examples under :ref:`title-detection-off` do, and
:meth:`~nameparser.Lexicon.readings_of` answers for one word. The
modules that exposed them as constants in 2.x (``nameparser.config.titles``,
``particles``, ``suffixes`` and the rest) are gone in 3.0, and
:doc:`migrate` gives the call or comprehension for each constant.
The Korean surname list, ``nameparser.config.surnames`` through 2.x
and private in 3.0, is the default lexicon's ``surnames``:
``Lexicon.default().surnames``.

Kinds and properties
~~~~~~~~~~~~~~~~~~~~~

A kind belongs to a category, which decides what the reading does:

.. list-table::
   :header-rows: 1
   :widths: 18 52 30

   * - Category
     - Kinds
     - Properties
   * - title
     - ``title``, ``salutation``, ``style``, ``academic``, ``religious``,
       ``nobility``, ``military``, ``office``, ``occupation``,
       ``kinship``, ``modifier``
     - ``addresses="given"``, ``after_given=True``,
       ``abbreviation=True``, ``attaches=[...]``
   * - suffix
     - ``suffix``, ``generation``, ``agnomen``, ``credential``,
       ``honorific``, ``professional_honorific``, ``status``,
       ``courtesy``
     - ``acronym=...``, ``attached="after"``, ``title_case_is_name=True``
   * - particle
     - ``particle``, ``preposition``, ``article``, ``patronymic``,
       ``teknonymic``, ``clan``, ``rank``, ``saint``, ``alias``
     - none
   * - conjunction
     - ``conjunction``
     - ``may_be_initial=True``
   * - bound_given
     - ``bound_given``
     - ``completed_by=[...]``
   * - relation
     - ``birth_marker``
     - none
   * - name
     - ``given``, ``family``
     - ``same_as="..."`` and ``after_particle=True`` on ``given``;
       ``shared=True`` on either

``nameparser/vocab/README.md`` in the repository says what each kind
and property means. A property given its unwritten value (``None``,
``False``) is removed; ``acronym`` is unwritten-true on a
``credential`` alone. Two things are not properties: whether a reading
is on (a caller's always is) and its case mask (:ref:`case-exceptions`).

A **name** reading beside another reading is what makes a word
ambiguous, as the vocabulary files mark it: a title with a ``given``
reading is a title only inside a phrase, a particle with one may be a
given name, and a credential or a generation word with a name reading
is read as the suffix only where the writing or the count says so
(:ref:`ambiguous-words`). So ``add("guru", kind="given")``
keeps ``Guru`` a title only inside a phrase, and
``remove("van", kind="given")`` makes ``van`` a particle that is never
a given name.

A reading is of one word, with two exceptions, so ``add`` refuses a
phrase of any other kind: a title addressing the given name
(``add("lt col", kind="title", addresses="given")``), matched against
the space-joined run of words already read as titles or by that run's
last word — several titles written together are one form of address
and the last one does the addressing, so ``"Her Majesty Queen
Elizabeth"`` is read by ``queen`` — and a birth marker, matched by
lookahead over the words as written: ``add("z domu",
kind="birth_marker")`` matches the pair and neither word alone, which
is how the shipped Polish entry works. The words have to stand
together — a bracketed clause or a comma between them ends the run, and
the first word is then an ordinary name word. Where a phrase and a word
starting it are both configured, the phrase wins where it matches and
the word matches everywhere else.

The limit is on what a reading holds, not on the shape a name can have.
Adjacent suffix words are reassembled after they match, so a multi-word
credential is reachable as its component words:

.. doctest::

    >>> parse("John Smith, MD PhD").suffix
    'MD PhD'

That has held since 1.4.0.

.. _title-detection-off:

Turning title detection off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``every=True`` with a kind and no words takes out every word's readings
of it, and the category ``"title"`` matches every title kind, so every
title reading goes at once. (A call with no words and no ``every``
raises, so an empty ``remove(*words, kind=...)`` never does this.)

.. doctest::

    >>> len(Lexicon.default().words(kind="title")) > 800
    True
    >>> lean = Lexicon.default().remove(kind="title", every=True)
    >>> lean.words(kind="title")
    ()
    >>> Parser(lexicon=lean).parse("Dean of Students Jane Smith").title
    ''
    >>> Parser(lexicon=lean).parse("Hon Solo").given
    'Hon'

Emptying the title vocabulary does not switch titles off entirely,
though. A word ending in a period, standing at the front of the part
that carries the given name, is read as a title structurally, without
consulting the vocabulary at all — that is what lets unfamiliar ranks
and abbreviations work (see :ref:`abbreviated-titles`):

.. doctest::

    >>> bare = Parser(lexicon=lean)
    >>> bare.parse("Professor John Smith").title      # vocabulary gone
    ''
    >>> bare.parse("Dr. John Smith").title            # structural, stays
    'Dr.'

Combining two lexicons
~~~~~~~~~~~~~~~~~~~~~~~

Whole lexicons compose with ``|`` — handy for keeping a shared house
vocabulary separate from a per-source one and combining them at parser
construction. The right-hand lexicon's edits apply after the left's,
so where the two disagree the later one wins; the ``surnames`` and
``given_names`` lists are unioned, and case masks taken right-biased:

.. doctest::

    >>> house = Lexicon.empty().add("dean", kind="office")
    >>> per_source = Lexicon.empty().add("provost", kind="academic")
    >>> both = house | per_source
    >>> [r.kind for w in ("dean", "provost") for r in both.readings_of(w)]
    ['office', 'academic']
    >>> [r.kind for r in (both | Lexicon.empty().remove("dean")).readings_of("dean")]
    []

.. _case-exceptions:

Fixing the case of a particular word
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``capitalization_exceptions`` is the one pair-valued field — each entry
maps a lowercase key to a *case mask*: the key's own letters and
digits, each in the case it should take (``"phd"`` → ``"PhD"``). Case
repair lays the mask over the word as it was written and keeps every
other character where it stood, so it recases a word and never
re-spells it. A value that spells anything else raises ``ValueError``
when the lexicon is built. Being a mask rather than a reading, it isn't
a fit for ``add()``/``remove()``. Change it with ``dataclasses.replace()``
instead, and pass the result to ``capitalized()``:

.. doctest::

    >>> import dataclasses
    >>> from nameparser import parse
    >>> str(parse("jane smith dclinpsy").capitalized())
    'Jane Smith Dclinpsy'
    >>> default = Lexicon.default()
    >>> lex = dataclasses.replace(
    ...     default,
    ...     capitalization_exceptions=tuple(default.capitalization_exceptions)
    ...     + (("dclinpsy", "DClinPsy"),))
    >>> str(parse("jane smith dclinpsy").capitalized(lex))
    'Jane Smith DClinPsy'
    >>> str(parse("JANE SMITH D.CLINPSY.").capitalized(lex))
    'Jane Smith D.ClinPsy.'

Note the ``tuple(...) + ...``: assigning a bare ``(("dclinpsy", "DClinPsy"),)``
would *replace* the default exceptions rather than extend them, so
the shipped masks (``phd``, ``bsc``, ``psyd`` and the rest) would be
lost and those words fall back to the all-capitals acronym repair:
``john smith phd`` would give ``John Smith PHD`` rather than
``John Smith PhD``.

A mask also outranks the lowercase that case repair gives a surname
particle (``de la Vega``). The shipped map uses that for the Irish
particles, which are written capitalized:

.. doctest::

    >>> str(parse("SEÁN Ó MURCHÚ").capitalized())
    'Seán Ó Murchú'
    >>> str(parse("JUAN DE LA VEGA").capitalized())
    'Juan de la Vega'

A saint's name and a German rank written inside the surname are
particles too, and are written with their capital without a mask:

.. doctest::

    >>> str(parse("JOHN ST CLAIR").capitalized())
    'John St Clair'
    >>> str(parse("MANFRED FREIHERR VON RICHTHOFEN").capitalized())
    'Manfred Freiherr von Richthofen'

Your own entry outranks it the same way, which is how to keep a
family's capitalized particle. A mask applies wherever its word stands,
though, so it recases every other name with that particle too:

.. doctest::

    >>> str(parse("martin van buren").capitalized())
    'Martin van Buren'
    >>> van_lex = dataclasses.replace(
    ...     default,
    ...     capitalization_exceptions=tuple(default.capitalization_exceptions)
    ...     + (("van", "Van"),))
    >>> str(parse("martin van buren").capitalized(van_lex))
    'Martin Van Buren'
    >>> str(parse("ludwig van beethoven").capitalized(van_lex))
    'Ludwig Van Beethoven'

Removing or replacing a shipped mask
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The shipped masks come with the vocabulary. Among them are the Gaelic
surnames opening Mac that most of their bearers write with the inner
capital (``MacDonald``, ``MacGregor``). Since 3.0, case repair
title-cases any other name opening Mac (``Machado``, ``Mackenzie``),
while ``Mc`` keeps its capital (``McDonald``).

A mask belongs to the word, not to one of its readings, so removing the
word's reading with ``remove()`` leaves the mask in place. To drop a
mask, filter its pair out of ``capitalization_exceptions``:

.. doctest::

    >>> str(parse("RONALD MACDONALD").capitalized())
    'Ronald MacDonald'
    >>> no_mac = dataclasses.replace(
    ...     default,
    ...     capitalization_exceptions=tuple(
    ...         pair for pair in default.capitalization_exceptions
    ...         if pair[0] != "macdonald"))
    >>> str(parse("RONALD MACDONALD").capitalized(no_mac))
    'Ronald Macdonald'
    >>> reading_gone = default.remove("macdonald", kind="family")
    >>> str(parse("RONALD MACDONALD").capitalized(reading_gone))
    'Ronald MacDonald'

To write a word some other way, append your own pair, as above. When
two pairs share a key, the later one replaces the earlier, so you don't
need to remove the shipped pair first:

.. doctest::

    >>> phd_caps = dataclasses.replace(
    ...     default,
    ...     capitalization_exceptions=tuple(default.capitalization_exceptions)
    ...     + (("phd", "PHD"),))
    >>> str(parse("john smith phd").capitalized(phd_caps))
    'John Smith PHD'

How a key matches a word
^^^^^^^^^^^^^^^^^^^^^^^^

The key is matched against the token with punctuation normalized away,
not against the raw text, so one ``"phd"`` entry covers ``phd``,
``PHD`` and ``Ph.D.`` alike, and you don't need a separate key for each
way a source might punctuate it. (A mixed-case ``Phd`` matches too, but
mixed case is left as written unless you pass ``force=True``; see
:ref:`rendering-arguments`.)

Each word keeps its own punctuation: ``Ph.D.`` repairs to ``Ph.D.``,
not ``PhD``. Punctuation in the *value* is never written into the word;
it only marks which of the mask's letters are joined. That matters for
one case: a single letter the writer split off beside a full stop is an
initial, and is capitalized even where the mask keeps that letter
inside a longer run:

.. doctest::

    >>> str(parse("john smith ph.d.").capitalized())
    'John Smith Ph.D.'
    >>> str(parse("john smith p.h.d.").capitalized())
    'John Smith P.H.D.'

Words that need no entry
^^^^^^^^^^^^^^^^^^^^^^^^

An acronym the lexicon holds as a credential, plain or dotted, and
a roman numeral are written in capitals by case repair on its own. Most
listed acronyms whose usual spelling is not all capitals already carry
a shipped mask (``DSc``, ``PsyD``, ``PharmD``, ``MDiv`` and others):

.. doctest::

    >>> str(parse("john smith md iv").capitalized())
    'John Smith MD IV'
    >>> str(parse("john smith psyd").capitalized())
    'John Smith PsyD'

The exception is an acronym that is also a name word, such as ``meng``
or ``edd``. A mask applies wherever its word stands, so it would
re-spell a person called Meng or Edd, and these get none: they repair
in plain capitals. The reasoning is the Excluded block for
``CAPITALIZATION_EXCEPTIONS`` (meng, edd, lac, ded) in
``docs/design/decisions/vocabulary-exclusions.md``.

.. doctest::

    >>> str(parse("john smith edd").capitalized())
    'John Smith EDD'

Acronyms the vocabulary doesn't list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An acronym the lexicon holds no reading of repairs according to how it
is written:

- **Plain** (``dclinpsy``), it parses as an ordinary name word and repairs
  as one: ``Dclinpsy``, as in the first example above.
- **Dotted** (``d.clinpsy.``), it is a suffix by shape alone (see
  :ref:`unlisted-credentials`) and repairs in all capitals the same as
  a listed acronym does: ``D.CLINPSY.``.

Either way, give it a credential reading, or a mask of its own,
rather than relying on this fallback.

.. _ambiguous-words:

Words that are also ordinary names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some vocabulary words are also ordinary name words: an acronym suffix
that is also borne as a surname, a particle that doubles as a given
name, a connective letter that doubles as an initial. What marks them is
a second reading beside the first: a ``given`` or ``family`` reading
beside a credential, a generation word or a particle, and the
``may_be_initial`` property on a one-letter connective. The second
reading adds no vocabulary by itself; it narrows how the word is read
when it appears alone, and the parse reports the fork as an ambiguity.
A title with a ``given`` reading works differently, being a title only
inside a phrase (:ref:`titles-also-given-names`).

A plain choice of languages keeps every name reading, and a strict one
(:ref:`strict-choice`) every reading its chosen files and the shared
``mul`` file hold, so neither settles these words where the chosen
language's own file, or the ``mul`` file, holds both readings. English
lists ``ma`` as a credential and as a surname, so a strict English
choice still reads ``JOHN SMITH MA`` by the count and reports it, and
Dutch lists ``van`` as a particle and as a given name. A choice ends
such a fork where it switches off another language's vocabulary
reading of the word (below), and a strict choice also wherever one of
the two readings of a word in Latin letters sits in another language's
file: it keeps only the chosen files' and the ``mul`` file's readings
of such a word, dropping the others, name readings included (a word
written in another script keeps the readings a plain choice of the
same languages gives it). A strict Dutch choice reads ``JOHN SMITH MA`` family ``MA``,
and a strict Portuguese one ``Do Smith`` family ``Do Smith``, both
unreported. The recipes in this
section are the way to settle the rest.

Credentials that are also surnames
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``ma`` is a shipped example: it holds a credential reading and the
name readings of a common surname. Written
with its periods it is a suffix outright; written bare, the
capitalization decides:

.. doctest::

    >>> parse("Jack Ma").family
    'Ma'
    >>> parse("Jack M.A.").suffix
    'M.A.'
    >>> parse("Jack MA").suffix
    'MA'

The full reading of a bare marked acronym, in order:

- **ALL CAPITALS** in a mixed-case name leans to the credential: it is
  a suffix even with no words to spare (``"Jack MA"``). The capitals
  settle it as the periods do, so no ambiguity is reported, and a word
  after it in the given part after a family comma reads as part of
  the suffix (``"Smith, John MA Jones"`` gives suffix ``MA Jones``).
- **Title-case** in a mixed-case name leans to the surname: it stays
  the family name even WITH words to spare (``"John Smith Ma"``).
- **No signal** — all lowercase in a mixed-case name, or any spelling
  in a name written wholly in one case — falls back to the count: a
  suffix with two or more words before it, not counting a title or a
  nickname (``"John Smith ma"``), the family name otherwise
  (``"JACK MA"``).
- **After a comma** the count of name words before the comma decides
  FIRST, and the case is read only where the count leaves the word a
  name. ``"John Smith, Ba"`` reads suffix ``Ba`` on the count alone, and
  ``"Smith, BA"`` reads suffix ``BA`` on the capitals lean. What still
  reads as the given name is ``"Smith, Ba"`` (one word, and Title-case
  has no credential lean) and ``"smith, ba"`` (one word, one case, no
  lean at all).
- **In brackets after the name**, the capitals in a mixed-case name
  settle it as the credential too, and so does a period inside the word:
  ``"John Smith (BA)"`` and ``"John Smith (B.A)"`` give suffix ``BA`` and
  ``B.A``. Any other spelling there, and any spelling inside the name,
  falls through to nickname parsing (``"John Smith (Ba)"``,
  ``"Jeffrey (JD) Bricken"``), reported as a ``suffix-or-nickname``
  ambiguity.

Generation words that are also surnames
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A name reading beside a suffix word does the same: French ``fils`` and
the Brazilian agnomens ``Filho``, ``Neto`` and ``Sobrinho`` mark a
generation, and each is a surname too. An agnomen (the ``agnomen``
kind), written in the case of the name around it, is a suffix only
where the name keeps a word for its family. The
writing of ``fils`` speaks as well: in a mixed-case name a Title-case
``Fils`` is the family name even with a word to spare:

.. doctest::

    >>> parse("Pedro Alves Neto").suffix
    'Neto'
    >>> parse("Ana Neto").family
    'Neto'
    >>> parse("Marie Fils").family
    'Fils'

A caller whose data writes an agnomen as part of the surname takes out
its suffix reading, leaving its name reading:

.. doctest::

    >>> kept = Lexicon.default().remove("neto", kind="agnomen")
    >>> Parser(lexicon=kept).parse("Pedro Alves Neto").family
    'Neto'

Mark a word, or leave it out
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you add a word that is both a credential and a name, weigh how
often it is one against the other. There are three choices, and none is
free:

- **A credential alone**: the credential reading is taken silently,
  and a wrong claim can lose a real person's surname.
- **A credential and a name reading**: the reading depends on the
  writing as above, and every bare reading reports the fork.
- **No credential reading at all**: right when the name reading is far
  more common, as for an acronym whose credential is tenuous or
  specialized beside a common surname. That is what the default
  vocabulary did with ``rai`` and ``cha`` in 2.3; a caller who needs
  one adds it back with ``Lexicon.default().add("cha",
  kind="credential")``.

Where the credential reading is another language's, choosing the
language settles the word with no edit. English lists ``DO`` as a
credential (Doctor of Osteopathy), and Portuguese lists ``do`` as a
particle, so choosing Portuguese switches the credential reading off
and a trailing ``DO`` is a name word, with no fork left to report
(:ref:`choosing-languages`):

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> parse("JOSE SILVA DO").suffix, parse("JOSE SILVA DO").ambiguities
    ('DO', (Ambiguity('suffix-or-name': 'DO'),))
    >>> portuguese = parser_for(locales.PT).parse("JOSE SILVA DO")
    >>> portuguese.family, portuguese.ambiguities
    ('DO', ())

.. _titles-also-given-names:

Titles that are also given names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Many titles are borne as given names too: ``Dean``, ``King``,
``Prince``, ``Grace``, ``Major``, ``Sheikh``. A title addresses the
name after it, so at the front of a name there is no count of words to
read, and what tells the person ``Dean Smith`` from the office in
``Dean of Students`` is the phrase the word stands in. Since 2.7 these
words hold a ``given`` reading beside their title reading, and each is
a title only inside a title phrase: behind a style
(``His Majesty King``) or a modifier (``Associate Dean``), before
``of`` (``Dean of Students``), or in a listed two-word phrase
(``Major General``). Anywhere else it is a name word:

.. doctest::

    >>> parse("Dean Smith").given
    'Dean'
    >>> parse("Associate Dean Smith").title
    'Associate Dean'
    >>> parse("Dean of Students Jane Smith").title
    'Dean of Students'
    >>> parse("Major General John Smith").title
    'Major General'

A language can run the other way, holding a given-name reading of a
title that its file leaves off until the language is chosen. ``Lady``
is a given name under a Spanish choice (``locales.ES``), ``Hon`` under
a Chinese choice of languages (a :class:`~nameparser.Locale` with
``languages=frozenset({"zh"})``; the ``zh`` pack makes none, so it
leaves ``Hon`` a title), and ``Guru`` under ``locales.NE``, each staying a title
inside a phrase; :ref:`choosing-languages` shows the first two, and the table of shipped
packs in :doc:`locales` the third.

Where such a word opens the name and a listed phrase could have held
it, the parse reports a ``title-or-name`` ambiguity, its alternative
the title reading (:ref:`reading-not-taken`). A word no listed phrase
holds, such as ``Grace`` (a title in ``His Grace``), reports nothing
standing alone:

.. doctest::

    >>> dean_alt = parse("Dean Smith").ambiguities[0]
    >>> dean_alt.kind.value, dean_alt.alternative.kind.value
    ('title-or-name', 'title')
    >>> parse("Grace Smith").ambiguities
    ()

Four things in the readings make this vocabulary:

- A ``given`` reading beside a title reading makes the title one read
  only inside a phrase; removing it, as the first example on this page
  does, reads the word as a title everywhere.
- The ``modifier`` kind is a word that qualifies a head title
  (``associate``, ``vice``).
- The ``style`` kind is a form of address a title may stand behind
  (``majesty``, ``highness``, ``excellency``).
- ``attaches`` on a title reading names the title kinds, or the title
  words, it makes a two-word phrase with, each phrase read only where
  both words are titles. Narrowing it reads the words of a phrase it
  no longer reaches apart:

.. doctest::

    >>> parse("Chief Justice John Roberts").title
    'Chief Justice'
    >>> [r.properties for r in Lexicon.default().readings_of("chief")]
    [(('attaches', ('military', 'office')),)]
    >>> chief = Lexicon.default().add("chief", kind="nobility",
    ...                               attaches=["military"])
    >>> Parser(lexicon=chief).parse("Chief Justice John Roberts").title
    'Chief'
    >>> Parser(lexicon=chief).parse("Chief Sergeant John Roberts").title
    'Chief Sergeant'

Particles that are also given names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A ``given`` reading is the same idea for surname particles. A particle
holding one may also be a given name, which is what makes a leading
one a decision to take; a particle *without* one never is, so there is
nothing to decide. That shows up in what a particle
standing *alone* at the front of a name does: a listed one is a name
part in its own right, while one without pulls the rest of the
name into the surname and leaves no given name at all. Which field a
particle that may be given lands in is ``name_order``'s question,
covered below; one that may not, opening the name, is the surname
under every order, because a word that can never be a given name leaves the order
nothing to decide.

.. doctest::

    >>> parse("van Gogh").given          # 'van' may be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' may not
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

A comma forestalls the question rather than answering it. Writing the
surname before the comma has already said which words are the surname,
so a particle at the front of them decides nothing, and whatever
follows the comma is the given name as usual:

.. doctest::

    >>> parse("de Mesnil, Juan").given   # the comma named the surname
    'Juan'

If your data never uses ``Van`` as a given name, take out its
``given`` reading: a leading ``van`` is then no decision at all, so no
ambiguity is recorded and it becomes part of the surname — under any
``name_order``, since that is what taking the word out asserted:

.. doctest::

    >>> lex = Lexicon.default().remove("van", kind="given")
    >>> Parser(lexicon=lex).parse("van Gogh").family
    'van Gogh'

For particles the default runs the other way from credentials: a
particle that is not borne as a given name holds no ``given`` reading,
which is where ``mc`` and ``ste`` were moved (#360).

.. _connectives-also-initials:

One-letter connectives that are also initials
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``may_be_initial`` is the same idea for one-letter connectives.
A single letter written against the name's own case is an initial and
one written with it is the connective — but a name written wholly in
one case, all upper or all lower, says nothing either way, and this is
the property that decides it there. ``e`` and ``i`` are the two
connectives shipped with it: a bare ``E`` or ``I`` initial is common where those letters
between two surnames are rarer, and ``y`` runs the other way, so ``y``
joins even written as a bare capital.

.. doctest::

    >>> parse("jose e maria santos").middle       # 'e' reads as an initial
    'e maria'
    >>> parse("JUAN GARCIA Y LOPEZ").family       # 'y' joins
    'GARCIA Y LOPEZ'
    >>> parse("Jose e Maria Santos").given        # mixed case decides itself
    'Jose e Maria'

Such a connective also reports the fork, so a caller can see which reading was
taken:

.. doctest::

    >>> [a.kind for a in parse("jose e maria santos").ambiguities]
    [<AmbiguityKind.CONJUNCTION_OR_INITIAL: 'conjunction-or-initial'>]

If you know your data's language, choose it rather than editing the
words one at a time: a chosen language's connective is a connective
even in a name written in one case, and the fork is no longer reported.
For Portuguese ``e``, use the ``pt`` pack (``locales.PT_BR`` reads it the
same way):

.. doctest::

    >>> from nameparser import Locale, locales, parser_for
    >>> parser_for(locales.PT).parse("jose e maria santos").given
    'jose e maria'
    >>> parser_for(locales.PT).parse("jose e maria santos").ambiguities
    ()

Catalan and Polish ``i`` link two surnames the way ``y`` does in
Spanish. Neither has a pack, but a :class:`~nameparser.Locale` that
only chooses the language (``"ca"`` or ``"pl"``) does the same for
them (see :ref:`choosing-languages`):

.. doctest::

    >>> catalan = Locale(code="ca", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"ca"}))
    >>> parse("josep carod i rovira").family
    'rovira'
    >>> parser_for(catalan).parse("josep carod i rovira").family
    'carod i rovira'

Spanish ``y`` needs no choice: it is a connective by default, so
``locales.ES`` leaves it as it is. A choice settles every word the
language holds, not only its connective (``pt`` reads ``do`` as a
particle, never the DO credential); to change one connective and
nothing else, set ``may_be_initial`` on the word itself — for ``e``,
``Lexicon.default().add("e", kind="conjunction", may_be_initial=False)``.

If your data is Dutch, where a bare single letter is an initial and
never a connective, add the other one instead:

.. doctest::

    >>> lex = Lexicon.default().add("y", kind="conjunction",
    ...                             may_be_initial=True)
    >>> Parser(lexicon=lex).parse("juan garcia y lopez").middle
    'garcia y'

Bound given names
~~~~~~~~~~~~~~~~~~

A ``bound_given`` reading is a given-name prefix that attaches to the
following word to form one given name — ``abdul``, ``abu``, ``umm`` and
their Arabic-script spellings (``عبد``, ``أبو``, ``أم``) among them:

.. doctest::

    >>> parse("abdul salam ahmed salem").given
    'abdul salam'

Add your own, or take out every one to switch the behavior off
entirely:

.. doctest::

    >>> lex = Lexicon.default().add("mohamad", kind="bound_given")
    >>> Parser(lexicon=lex).parse("mohamad salam ahmed salem").given
    'mohamad salam'
    >>> off = Lexicon.default().remove(kind="bound_given", every=True)
    >>> Parser(lexicon=off).parse("abdul salam ahmed salem").given
    'abdul'

Past the first name word, a bound word joins only a word its reading
lists in ``completed_by``. Arabic-script ``عبد`` lists the names of God
and the devotional names it completes, so the pair is one name wherever
it stands, while the Latin ``abdul`` lists none:

.. doctest::

    >>> parse("طارق عبد العزيز").family
    'عبد العزيز'
    >>> parse("Tariq Abdul Aziz").family
    'Aziz'
    >>> lex = Lexicon.default().add("abdul", kind="bound_given",
    ...                             completed_by=["aziz"])
    >>> Parser(lexicon=lex).parse("Tariq Abdul Aziz").family
    'Abdul Aziz'

Behavior: Policy
-----------------

When your data source or application needs different parsing behavior
— a different name order, stricter suffix rules, extra delimiters —
set it on :class:`~nameparser.Policy`, a small, closed set of fields,
listed below.

.. list-table::
   :header-rows: 1
   :widths: 22 28 50

   * - Field
     - Type
     - Effect
   * - ``name_order``
     - one of the three exported order constants
     - Assigns positional input to given/middle/family in this order:
       ``GIVEN_FIRST`` (default), ``FAMILY_FIRST`` or
       ``FAMILY_FIRST_GIVEN_LAST``. A family comma overrides it. See
       :ref:`name-order`.
   * - ``script_orders``
     - pairs of ``Script`` and an order
     - Assigns a name in one of these scripts in the paired order,
       whatever ``name_order`` says. Defaults to family-first for a
       name wholly in Han or Hangul, or in kanji and kana other than
       katakana alone. See
       :ref:`east-asian-defaults`.
   * - ``segment_scripts``
     - ``frozenset[Script]``
     - Scripts whose unspaced names are split into surname and given
       name. Defaults to Hangul. See :ref:`east-asian-defaults`.
   * - ``patronymic_rules``
     - ``frozenset[PatronymicRule]``
     - Reorders patronymic-shaped names via opt-in detectors — East
       Slavic formal order (``EAST_SLAVIC``) or Turkic reversed order
       (``TURKIC``) — but stands down under a declared
       ``FAMILY_FIRST`` or ``FAMILY_FIRST_GIVEN_LAST`` ``name_order``.
       Each rule also fills ``ParsedName.patronymic``, reading a middle
       name with the East Slavic ending, and a Turkic marker with the
       word before it. Defaults to empty.
   * - ``middle_as_family``
     - ``bool``
     - Folds ``middle`` into ``family`` instead of splitting them —
       for naming systems with no middle-name concept. Defaults to
       ``False``.
   * - ``two_family_names``
     - ``bool``
     - Reads the last two name words as the family name, for data
       where people carry two family names (Spain, most of Latin
       America). Defaults to ``False``. See :ref:`two-family-names`.
   * - ``two_given_names``
     - ``bool``
     - Reads the middle name beside the given name as part of it, for
       data where people carry a compound given name and no middle
       name (``María José``). Defaults to ``False``. See
       :ref:`two-given-names`.
   * - ``lone_name_word``
     - ``Role.GIVEN`` or ``Role.FAMILY``
     - The field a name of one word reads as, under every
       ``name_order``. Defaults to ``Role.GIVEN``. See
       :ref:`lone-name-word`.
   * - ``nickname_delimiters``
     - ``frozenset[tuple[str, str]]``
     - Routes content enclosed by these delimiter pairs to
       ``nickname``. Defaults to
       :data:`~nameparser.DEFAULT_NICKNAME_DELIMITERS` — straight
       quotes and parentheses plus the typographic conventions (smart
       quotes, guillemets, CJK brackets, ...). See :ref:`brackets`.
   * - ``maiden_delimiters``
     - ``frozenset[tuple[str, str]]``
     - Routes content enclosed by these delimiter pairs to ``maiden``
       instead of ``nickname``. Needed only for a clause that does not
       announce itself: ``"(née Jones)"`` is a maiden name without it.
       Defaults to empty. See :ref:`brackets`.
   * - ``extra_suffix_delimiters``
     - ``frozenset[str]``
     - Adds separators that split suffix groups, e.g. ``" | "`` for
       ``"Jane Smith, RN | CRNA"``. Additions only — the comma, the
       semicolon, and a hyphen or slash standing alone split suffix
       groups after a whole name and cannot be replaced. See
       :ref:`suffix-delimiters`.
   * - ``lenient_comma_suffixes``
     - ``bool``
     - Reads an initial-shaped suffix word after a comma as a suffix:
       ``"John Smith, V"`` is John Smith the fifth when ``True``
       (default); ``False`` reads ``V`` as a given-name initial
       instead, and ``"john smith, v"`` the same way, since a name
       written all in one case reads as its capitals. Multi-letter
       suffixes (``III``, ``MD``) are unaffected.
   * - ``unlisted_dotted_suffixes``
     - ``bool``
     - Reads an unlisted dotted acronym such as ``X.Y.Z.`` as a
       credential where the name's shape allows it. Defaults to
       ``True``. See :ref:`unlisted-credentials`.
   * - ``unlisted_caps_suffixes``
     - :class:`~nameparser.CapsSuffixes`
     - Where an unlisted all-caps word such as ``XYZ`` reads as a
       credential: after a comma (``AFTER_COMMA``, the default), at the
       end of a name as well (``EVERYWHERE``), or nowhere (``OFF``).
       See :ref:`unlisted-credentials`.
   * - ``strip_emoji``
     - ``bool``
     - Excludes emoji from tokenization — they appear in no field or
       rendered view, though ``original`` keeps them. Defaults to
       ``True``. See :ref:`strip-flags`.
   * - ``strip_bidi``
     - ``bool``
     - Excludes bidirectional control characters the same way.
       Defaults to ``True``. See :ref:`strip-flags`.

To apply a :class:`PolicyPatch <nameparser.PolicyPatch>` directly --
without going through a locale pack -- call :meth:`Policy.patched()
<nameparser.Policy.patched>`:

.. doctest::

    >>> from nameparser import Policy, PolicyPatch
    >>> Policy().patched(PolicyPatch(middle_as_family=True))
    Policy(middle_as_family=True)

.. _name-order:

Family-first name order
~~~~~~~~~~~~~~~~~~~~~~~~

``name_order`` is the one most likely to matter for data that is not
in Western order. Positional input is assigned in the order you
declare — with the three vocabulary exceptions noted under
:ref:`order-vocabulary-first` — so a name written family-first —
Hungarian, here — parses as written instead of needing to be
rearranged afterwards:

.. doctest::

    >>> from nameparser import Parser, Policy, FAMILY_FIRST, parse
    >>> parse("Nagy Laszlo Peter").family            # default GIVEN_FIRST
    'Peter'
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> name = family_first.parse("Nagy Laszlo Peter")
    >>> name.family, name.given, name.middle
    ('Nagy', 'Laszlo', 'Peter')

An explicit comma still wins, on the reasoning that someone who wrote
one meant it — so the same parser reads ``"Thomas, John"`` as
family-then-given regardless of the configured order:

.. doctest::

    >>> family_first.parse("Thomas, John").family
    'Thomas'

A comma that only sets off suffixes leaves the order governing the
name before it:

.. doctest::

    >>> family_first.parse("Smith John, Jr.").given
    'John'

A Vietnamese full name needs a third order. It is written family, then
middle, then given — the name a person is actually called by is the
*last* word, not the second. Family-first order gets the family name
right and then reverses the remaining two, so
``FAMILY_FIRST_GIVEN_LAST`` exists for the names that read this way:

.. doctest::

    >>> from nameparser import FAMILY_FIRST_GIVEN_LAST
    >>> family_first.parse("Tran Quoc Toan").given       # FAMILY_FIRST
    'Quoc'
    >>> given_last = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    >>> viet = given_last.parse("Tran Quoc Toan")
    >>> viet.family, viet.middle, viet.given
    ('Tran', 'Quoc', 'Toan')

Nothing keys this order to a script the way the East Asian defaults
below do — Vietnamese is written in the Latin alphabet, which carries
no order of its own — so it applies only where you set it. For
Vietnamese data, the ``vi`` pack (``parser_for(locales.VI)``) sets this
order and also keeps the Vietnamese syllables other languages read as
particles or connectives (``Van``, ``Le``, ``Do``, ``The`` and others)
as name words, and ``Chi``, ``Ba`` and ``Do`` out of the credentials (see
:ref:`vietnamese-names`);
the bare ``Policy`` above is for data that wants the order alone.

``name_order`` describes where the data came from, not the language
of the people in it. Many administrative records list the family name
first whatever language the names are in: French lists write
``DUPONT Jean``, and Algerian ones follow the same convention in
Arabic script as well as in Latin, so a candidate list writes Salima
Bouzid as ``بوزيد سليمة``. Nothing in the name says which order it is
in, and the capitals in ``DUPONT`` don't count as a signal either, so
the order has to come from knowing the source:

.. doctest::

    >>> parse("بوزيد سليمة").given                    # default GIVEN_FIRST
    'بوزيد'
    >>> bouzid = family_first.parse("بوزيد سليمة")
    >>> bouzid.family, bouzid.given
    ('بوزيد', 'سليمة')

A locale pack could not supply this order for Arabic or French names,
because the same names are written given-first in running text. The
order belongs to the record, so it goes in a ``Policy`` you choose for
that source.

Declaring the order settles where a surname ends
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A surname particle joins forward, onto the word after it. Where a
particle *ends* the name there is nothing ahead of it to join, and what
it belongs to is decided by what the writing says rather than by the
word. Two things say it, and both amount to someone stating that the
family name came first — a family comma, and a declared family-first
order:

.. doctest::

    >>> parse("Jong, Anke de").family                  # the comma says so
    'de Jong'
    >>> family_first.parse("Jong Anke de").family      # the order says so
    'de Jong'

The comma and the order are one shape
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

That pair is not a coincidence but one shape written two ways: form 4
(``Title Family Given Middle Middle [Particle] [, Suffix]``) is form 2
(``[Title] Family [Suffix], Title Given (Nickname) Middle Middle[,]
Suffix [, Suffix]``) with the comma removed and the family folded inline —
titles included, so a title that form 2 writes after the comma leads
the name in form 4 instead. If your records are family-first without
commas, ``Policy(name_order=FAMILY_FIRST)`` reads them the way the
comma format is already read. Measured over the whole particle
vocabulary — every particle nameparser ships, crossed with three
families and three given names, 630 generated pairs in all — 603 of
630 agree (2026-08-30); the executable form of this correspondence is
``tests/v2/test_order_correspondence.py``.

Where the correspondence stops
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Three limits keep that statement honest:

- **It covers one shape, not comma deletion in general.** A name whose
  shape changes when the comma is removed — a title or suffix crossing
  to a different position — parses as the shape it becomes, not as a
  disagreeing reading of form 2.
- **A word that is both particle and suffix reads differently in the two
  writings.** The shipped words in both vocabularies are ``do``,
  ``mc`` and ``vd`` (2026-10-02). The
  particle attachment outranks the suffix reading on the comma side
  alone — that is the scope the rule is stated in — so
  ``parse("Ménil, Christophe vd")`` reads family ``vd Ménil``, while
  ``family_first.parse("Ménil Christophe vd")`` reads family ``Ménil``
  and suffix ``vd``. It is that asymmetry, not a precedence, that
  breaks the correspondence, and a listing ending in one of those words
  is the whole of the 27 disagreeing pairs measured above, not scatter.
- **Only** ``FAMILY_FIRST`` **is reached.** It is the only order that
  puts a trailing piece in the *middle*, where a particle means nothing.
  ``FAMILY_FIRST_GIVEN_LAST`` puts it in the given slot, where your own
  declaration already says it is the given name, and no comma format
  writes the given name last, so form 5 has no comma twin to correspond
  to in the first place:

.. doctest::

    >>> given_last.parse("Nguyen Thi Van").given
    'Van'

Where a leading particle run stops
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The declaration also bounds how far a *leading* particle run reaches.
With no order declared, nothing marks where the surname ends and a
particle followed by several words really can be all surname, so the
whole name is read as one. Declaring family-first asserts that what
follows the family is not more surname, which settles it:

.. doctest::

    >>> parse("de Mesnil Jean").family                 # nothing says where it ends
    'de Mesnil Jean'
    >>> family_first.parse("de Mesnil Jean").family    # the order does
    'de Mesnil'
    >>> family_first.parse("de Mesnil Jean").given
    'Jean'

In the default order, write the comma for that reading. Under a
family-first order the run stops after one name *word* rather than one
token, so it cannot cut inside a conjunction-joined run or a bound
given-name pair — ``"de la Vega y Santos Juan"`` keeps family
``de la Vega y Santos``. Where two or more words are left over, the two
family-first orders differ from each other:

.. doctest::

    >>> family_first.parse("de la Cruz Juan Carlos").middle
    'Carlos'
    >>> given_last.parse("de la Cruz Juan Carlos").middle
    'Juan'

.. _order-vocabulary-first:

Where the vocabulary answers first
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In three places the vocabulary layer answers before ``name_order`` is
consulted at all:

- **A middle word that is also a shipped particle** is claimed by the
  vocabulary. That is why the Vietnamese example above is not the more
  obvious ``"Nguyen Van Minh"``: ``Van`` is the Dutch particle ``van``,
  so that name reads family ``Nguyen`` with ``Van Minh`` given under
  *both* family-first orders, and the choice between them makes no
  difference. The ``vi`` pack takes the particle reading out, so under
  it the name reads middle ``Van``, given ``Minh``.
- **A never-given particle opening the name** overrides the declared
  order outright: where a particle that can never be a given name
  stands alone as the opening piece, the whole name is the surname, in
  every ``name_order``. ``"de Mesnil"`` is family ``de Mesnil`` under
  both family-first orders exactly as it is by default, not family
  ``de`` with ``Mesnil`` given — a word that can never be a given name
  leaves the order nothing to decide. A particle that *can* be a
  given name does this only under a family-first order, and only
  written in lower case beside capitals (since 3.0): ``"van Gogh"``
  reads family ``van Gogh`` there, while ``"Van Gogh"`` reads family
  ``Van``, given ``Gogh``, its capital leaving a real question to
  answer. Under the default order the particle is the given name in
  both spellings.
- **A lone name word beside a given-name title** is the given name in
  every ``name_order`` (since 2.5): ``"Sir John"`` reads given ``John``
  under both family-first orders, as it does by default, while
  ``"Dr John"`` still reads family ``John`` there.

`Words that are also ordinary names`_ covers dropping a word from a
vocabulary, or moving one between those two sets.

.. _lone-name-word:

Names written as one word
~~~~~~~~~~~~~~~~~~~~~~~~~

A name of one word gives the order nothing to compare, so nothing in
it says whether the word is a given name or a family name. The parser
reads it as the given name, under every ``name_order``, and reports the
choice as a ``given-or-family`` ambiguity:

.. doctest::

    >>> from nameparser import Role
    >>> parse("Anh").given
    'Anh'
    >>> family_first.parse("Anh").given
    'Anh'
    >>> [a.kind.value for a in family_first.parse("Anh").ambiguities]
    ['given-or-family']

Which field a word written alone fills depends on where the data came
from rather than on the order its longer names are written in: a list
of the names people go by holds given names, a column of surnames
holds family names. For data whose lone words are surnames, set
``lone_name_word``:

.. doctest::

    >>> surnames = Parser(policy=Policy(lone_name_word=Role.FAMILY))
    >>> surnames.parse("Nguyen").family
    'Nguyen'
    >>> surnames.parse("John Smith").family          # longer names unchanged
    'Smith'

Anything that does decide the word still decides it first, whatever the
switch says: a title (``"Mr. Johnson"`` is family ``Johnson``, ``"Sir
John"`` given ``John``), a nickname or maiden name beside it, and a
Han or Hangul name, which its script reads family-first. Through 2.x
the field followed ``name_order``, so a family-first order read a
lone word as the family name.

.. _two-family-names:

Names with two family names
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In Spain and most of Latin America a person carries two family names,
the father's first and then the mother's, and writes both after the
given names: Gabriel García Márquez's family name is ``García
Márquez``. Written given-first, that name has the same shape as a name
with a middle name, so the default reads the first family name as a
middle name:

.. doctest::

    >>> gabo = parse("Gabriel García Márquez")
    >>> gabo.middle, gabo.family
    ('García', 'Márquez')

``two_family_names=True`` reads the last two name words as the family.
Given names before them stay given and middle names, a particle counts
with the word it attaches to, titles and suffixes are not counted, and
an initial written alone never joins the family:

.. doctest::

    >>> two_names = Parser(policy=Policy(two_family_names=True))
    >>> two_names.parse("Gabriel García Márquez").family
    'García Márquez'
    >>> ana = two_names.parse("Ana María García López")
    >>> ana.given, ana.middle, ana.family
    ('Ana', 'María', 'García López')
    >>> two_names.parse("Dr. Juan Pérez de la Vega Jr.").family
    'Pérez de la Vega'

``surname2`` names the second of the two, which ``family`` keeps, and
``surname1`` the first, which a caller addressing or filing by it reads
(``surname1_base`` without its particles); a name the switch reads as
one family has no ``surname2``, and its ``surname1`` is the family:

.. doctest::

    >>> ana.surname2, ana.surname1
    ('López', 'García')
    >>> two_names.parse("Ana María García-López").surname2
    ''

A family that already holds two names keeps what it has, whether a
hyphen or ``y`` joins them (``"Ana María García-López"``, ``"José
Ortega y Gasset"``) or a particle chain took them both (``"Ana María de la Vega
Rodríguez"`` reads family ``de la Vega Rodríguez``). A name of two words is unchanged, and a comma naming the family
decides by itself, so ``"García López, Ana"`` needs no switch at all. Under a family-first ``name_order`` the *first* two
name words are the family.

Turn it on only for data written this way. A name with one family name
behind two given names, ``"Juan Carlos Pérez"``, loses ``Carlos`` to
the family under the switch, and Argentine names, which carry one
family name, are mostly that shape. Portuguese and Brazilian names
carry two family names too, the mother's first, but the people who
write them often give the last one alone as their family name: among
the UK company register's 5,333 Portuguese filers the switch breaks
1,481 names and mends 1,221 (measured 2026-10-24), while among ORCID's
researchers working or living in Portugal, who split their own names
into its boxes, it mends 4,295 and breaks 2,034 of 20,000 (measured
2026-10-27): the two populations disagree, so measure the data you have
before switching it on. Filipino names often carry a middle name
between the given name and the family name, traditionally the mother's
maiden surname, and their bearers count it with their given names:
``"Maria Santos Reyes"`` has family ``Reyes``, which the switch reads
as ``Santos Reyes``. Among ORCID's researchers in the Philippines it
breaks 8,234 names of 20,000 and mends 265. The parser
reports nothing for the names the switch moves: the shape it reads is
the same either way.

A given name standing before the family is most of what the switch gets
wrong, as in ``"José Luis Pérez"``. Words that are given names and
rarely surnames tell the two shapes apart, so the switch leaves a word
listed in the lexicon's ``given_names`` where it stands, under any
``name_order``. The field is empty by default, so you supply the list
for your data, or choose ``locales.ES``, which turns the switch on and
carries 1,000 Spanish given names, a name written with ñ listed with
n too (``locales.ES_AR``, for Argentine names, carries 5,000; see
:ref:`spanish-portuguese-titles`); an entry
written without accents
matches the word with them:

.. doctest::

    >>> listed = Parser(policy=Policy(two_family_names=True),
    ...                 lexicon=Lexicon.default() | Lexicon(given_names={"luis"}))
    >>> two_names.parse("José Luis Pérez").family
    'Luis Pérez'
    >>> luis = listed.parse("José Luis Pérez")
    >>> luis.middle, luis.family
    ('Luis', 'Pérez')

List words that are given names and rarely surnames in your data: a
word common in both roles, such as ``Martín``, is better left off. A
listed word that is someone's surname, as given names sometimes are,
stays out of the family: written given-first it becomes a middle name,
and under a family-first ``name_order`` the second surname becomes the
given name or a middle name.

.. _two-given-names:

Names with a compound given name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Spanish or Portuguese given name is often two names, such as María
José or Juan Carlos, and its bearer has no middle name. The default
reads the second as a middle name, the English convention:

.. doctest::

    >>> carlos = parse("Juan Carlos Pérez")
    >>> carlos.given, carlos.middle
    ('Juan', 'Carlos')

``two_given_names=True`` gives the given name the middle name beside
it. Any middle names past it stay middle names, a family comma leaves
the part after it to the switch, and with ``two_family_names`` on too
the family takes its word first, so a name of four words reads two and
two:

.. doctest::

    >>> two_given = Parser(policy=Policy(two_given_names=True))
    >>> two_given.parse("Juan Carlos Pérez").given
    'Juan Carlos'
    >>> two_given.parse("Pérez, Juan Carlos Antonio").middle
    'Antonio'
    >>> both = Parser(policy=Policy(two_family_names=True,
    ...                             two_given_names=True))
    >>> mj = both.parse("María José García López")
    >>> mj.given, mj.middle, mj.family
    ('María José', '', 'García López')
    >>> both.parse("Gabriel García Márquez").given
    'Gabriel'

A given name a particle completes reads whole too. Where the
particle's words would otherwise run on into the family, the parser
reads them as a middle name, with or without the switch, if the
vocabulary marks the word behind the particle as a given name written
there (``after_particle``), and the switch then takes them into the
given name. The words marked are those whose reading, among the ORCID
researchers' names it changes, matches the boxes they filled at least
three times for each time it does not: from Spain and Spanish-speaking
America (``del Carmen``, ``de los Ángeles``, ``del Mar``, ``del
Pilar``), and from Portugal and Brazil (``de Lurdes``, ``das Graças``,
``de Cássia``, ``de Tarso``). A Portuguese word too rare to measure
(``da Piedade``) is read only under ``locales.PT`` and
``locales.PT_BR`` (see :ref:`language-packs`). A phrase too often a
surname to mark, as Portuguese ``do Carmo`` is, stays the family, the same shape as ``"João da Silva
Santos"``, and so does one opening with a saint (``"Domingo Santa María
González"``):

.. doctest::

    >>> parse("María del Carmen García").middle
    'del Carmen'
    >>> carmen = two_given.parse("María del Carmen García")
    >>> carmen.given, carmen.family
    ('María del Carmen', 'García')
    >>> two_given.parse("Maria do Carmo Silva").family
    'do Carmo Silva'

To mark a word of your own, add it with ``Lexicon.default().add("carmo",
kind="given", after_particle=True)``, which moves the default reading
too. The two switches also leave alone
the Sikh names Kaur and Singh, given to every Sikh woman and man and
written after the personal name: ``"Harpreet Kaur Dhillon"`` keeps
middle ``Kaur`` under either switch, as it does by default.

Turn it on only for data written this way: under it every name whose
second given word is a middle name gains it in the given name
(``"John Quincy Adams"`` gives given ``John Quincy``), and people
filling a form that has a middle-name box split their names the other
way. Among the UK company register's 6,089 Spanish filers, 31.8% of
names agree in every box by default and 15.7% with this switch on;
with ``two_family_names`` on, 80.2% without this switch and 55.0%
with it (measured 2026-10-30). ``middle`` keeps its meaning either way,
the given part's words after the given name; the switch moves no word
anywhere else and reports nothing.

.. _east-asian-defaults:

East Asian defaults, and turning them off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defaults key on the *script* a name is written in rather than on
anything you set: a name written wholly in Han or Hangul — or in kanji
and kana, unless it is katakana alone — is assigned family-first
(``script_orders``),
and an unspaced hangul name is split into surname and given name
against the shipped Korean census list (``segment_scripts``).
:ref:`east-asian-names` explains the naming conventions both rest on;
this section is how to switch them off. Two further behaviors are not
policy fields at all, and are covered last.

Switching off order and splitting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The two defaults switch off separately:

.. doctest::

    >>> parse("김민준").family                    # both defaults on
    '김'
    >>> positional = Parser(policy=Policy(script_orders=()))
    >>> positional.parse("김민준").family         # still split
    '민준'
    >>> unsplit = Parser(policy=Policy(segment_scripts=frozenset()))
    >>> unsplit.parse("김민준").family            # one token, not split
    '김민준'

The two switches interact, and clearing only ``script_orders``
produces a third behavior rather than the old one: the split still
runs, so ``김민준`` still becomes two tokens, and the positional
default then assigns them given-first — the surname lands in
``given``. To restore nameparser 2.0's reading exactly, clear both
fields.

.. note::

   Every field here is annotated with its canonical *storage* type
   rather than with everything the constructor accepts — the same as
   ``capitalization_exceptions``, and for the same reason: the
   annotation is what you get back when you READ the attribute, which
   is the commoner operation.

   The constructor is deliberately wider. It takes any mapping for
   ``script_orders``, any iterable of ``Script`` for
   ``segment_scripts``, and plain strings wherever a ``Role`` is
   wanted (``Role`` is a ``StrEnum`` precisely so that works). A
   dataclass cannot express those two types separately, so the
   examples in this guide use the spellings that check clean under
   mypy — ``()`` and ``frozenset(...)`` rather than ``{}`` and a bare
   set literal. The wider spellings parse identically; they just need
   a ``# type: ignore[arg-type]`` if you run a type checker.

Teaching the splitter a surname
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To teach the splitter a surname it doesn't ship with, join a lexicon
holding it to the ``surnames`` list, a list rather than readings since
it divides a name instead of gating a word:

.. doctest::

    >>> lex = Lexicon.default() | Lexicon(surnames={"김민"})
    >>> Parser(lexicon=lex).parse("김민준").family
    '김민'

Chinese surnames are deliberately absent from that default set,
because splitting Han text requires knowing Chinese from Japanese;
:doc:`locales` covers the opt-in ``zh`` pack that supplies them.

Japanese names
^^^^^^^^^^^^^^

The Japanese behaviors ride these same two fields, so they need no
switches of their own. ``script_orders=()`` clears the kana-licensed
entry along with the Han and Hangul ones, so a name in kanji and kana
reads given-first again:

.. doctest::

    >>> parse("山田 エミ").family
    '山田'
    >>> positional.parse("山田 エミ").given
    '山田'

``segment_scripts=frozenset()`` deactivates every script at once, which
also stops a parser consulting whatever segmenter it was given. The
segmenter has an off-switch of its own as well:
``Parser(segmenter=None)``, which is the default. See
:ref:`segmenter-contract` for what a segmenter is expected to do with
text it does not handle.

Behaviors no policy field controls
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two behaviors apply however both fields are set:

- **The katakana middle dot** ``・`` separates tokens the way a space
  does, decided in tokenization.
- **A glued honorific**, a listed CJK honorific at the end of a name
  token, is split off it. The honorific vocabulary carries its own
  license rather than borrowing a script's: every entry is a word that
  can never end a name, so there is no per-script question for
  ``segment_scripts`` to answer.

.. doctest::

    >>> both_off = Parser(
    ...     policy=Policy(script_orders=(), segment_scripts=frozenset()))
    >>> both_off.parse("マイケル・ジャクソン").family
    'ジャクソン'
    >>> both_off.parse("田中さん").suffix
    'さん'

The honorific vocabulary is the peel's off-switch. Taking the
``attached`` property off an honorific's reading leaves that honorific
glued, while the spaced form still reads it as a suffix:

.. doctest::

    >>> no_san = Parser(lexicon=Lexicon.default().add(
    ...     "さん", kind="honorific", attached=None))
    >>> no_san.parse("田中さん").family
    '田中さん'
    >>> no_san.parse("田中 さん").suffix
    'さん'

The suffix reading stays, so the word is still a suffix written apart.
Taking ``attached`` off every honorific is also how to opt out of what
the peel *costs* a non-ASCII parse: with none attached the peel stops
at its first check, whereas ``segment_scripts`` never gated it and so
cannot turn it off.

.. _brackets:

Nicknames, maiden names, and brackets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maiden markers
^^^^^^^^^^^^^^

A maiden name is usually announced by a marker word, and then it needs
no brackets and nothing configured:

.. doctest::

    >>> parse("Jane Smith née Jones").maiden
    'Jones'

:ref:`nicknames-and-maiden-names` in the usage guide covers how the
marked forms read. The marker words themselves are the
``birth_marker`` readings of a ``Lexicon``, shipped in several
languages (``Lexicon.default().words(kind="birth_marker")`` lists them).
Add your
own like any other word; a marker you add works bare and in brackets
alike:

.. doctest::

    >>> parse("Jane Smith formerly Jones").maiden       # not a marker
    ''
    >>> marked = Parser(
    ...     lexicon=Lexicon.default().add("formerly", kind="birth_marker"))
    >>> marked.parse("Jane Smith formerly Jones").maiden
    'Jones'
    >>> marked.parse("Jane Smith (formerly Jones)").maiden
    'Jones'

A multi-word entry such as the shipped ``z domu`` is matched as a
phrase, not word by word; see `Vocabulary: Lexicon`_ above.

How a bracketed clause is read
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A delimiter pair carries no meaning of its own, so what a clause
enclosed in one reads as is settled in steps, and the pair is asked
last:

1. **A clause of credentials, generations or titles** is taken first
   and set apart from the name: each word becomes the suffix or the
   title its vocabulary makes it, and the name around it reads as it
   would beside a nickname. Other content ending in a period loses its
   brackets and parses as if it had been written bare.
2. **A clause that announces itself**, opening with a recognized maiden
   marker and carrying a word after it, is a maiden name inside any
   configured pair, with nothing configured (since 2.2). The marker is
   dropped from the value.
3. **Everything else is decided by the pair**: content in a
   ``nickname_delimiters`` pair is a nickname, and content in a
   ``maiden_delimiters`` pair is a maiden name.

.. doctest::

    >>> name_jr = parse("Jane Smith (née Jr.)")         # step 1, period
    >>> name_jr.family, name_jr.suffix
    ('née', 'Jr.')
    >>> parse("John Smith (PhD) Withers").family        # step 1
    'Withers'
    >>> parse("Jane Smith (née Jones)").maiden          # step 2
    'Jones'
    >>> parse('Jane Smith "née Jones"').maiden          # step 2, any pair
    'Jones'
    >>> parse("Jane (Jones) Smith").nickname            # step 3
    'Jones'

Routing a pair to maiden names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 3 is what ``maiden_delimiters`` is for. It reaches two kinds of
clause, not one: content with no marker word in it, such as a birth
surname written bare in parentheses, and a lone marker word. Listing a
pair in ``maiden_delimiters`` drops it from the effective
``nickname_delimiters`` set automatically, and the one-liner is the
whole recipe:

.. doctest::

    >>> policy = Policy(maiden_delimiters=frozenset({("(", ")")}))
    >>> Parser(policy=policy).parse("Jane (Jones) Smith").maiden
    'Jones'

A marker is dropped from the value only where it stands as its own
word with a name word after it. A lone marker is kept as the value —
and so is a multi-word one filling the clause, such as ``z domu`` —
and so is a marker written against the name it marks, which is one
token with it, so ``旧姓`` stays in the value too:

.. doctest::

    >>> parse("Jane Smith (Nee)").nickname
    'Nee'
    >>> Parser(policy=policy).parse("Jane Smith (Nee)").maiden
    'Nee'
    >>> Parser(policy=policy).parse("Jane Smith (z domu)").maiden
    'z domu'
    >>> cjk_parens = frozenset({("（", "）")})       # full-width
    >>> cjk = Parser(policy=Policy(maiden_delimiters=cjk_parens))
    >>> cjk.parse("山田花子（旧姓佐藤）").maiden
    '旧姓佐藤'

Adding a delimiter pair
^^^^^^^^^^^^^^^^^^^^^^^

To *add* a delimiter pair rather than reroute one, build on the
exported default — assigning a bare set replaces the built-in pairs
instead of extending them, the same trap as ``capitalization_exceptions``:

.. doctest::

    >>> from nameparser import DEFAULT_NICKNAME_DELIMITERS
    >>> parse("Benjamin {Ben} Franklin").middle        # not a pair by default
    '{Ben}'
    >>> policy = Policy(
    ...     nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("{", "}")})
    >>> Parser(policy=policy).parse("Benjamin {Ben} Franklin").nickname
    'Ben'

.. _suffix-delimiters:

Suffixes not separated by commas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A comma is the usual separator between post-nominals, but sources write
others. A few are read with no configuration, any other can be
declared, and a credential joined to another, or split by a space,
needs neither.

Separators read without configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A semicolon separates post-nominals as a comma does. Glued to the word
before it, it stays in the suffix as written:

.. doctest::

    >>> name = parse("Jane Smith, RN; CRNA")
    >>> name.given, name.family, name.suffix
    ('Jane', 'Smith', 'RN; CRNA')

So does a hyphen or a slash standing alone, with a space on each side,
after a whole name and its comma or after a further comma (since 2.7).
It is dropped, as a comma between suffixes would be:

.. doctest::

    >>> name = parse("Jane Smith, RN - CRNA")
    >>> name.given, name.family, name.suffix
    ('Jane', 'Smith', 'RN, CRNA')
    >>> parse("Jane Smith, Dr. / MD").given
    'Jane'

Glued to a word, a hyphen or slash is the word's own, so
``Jane Smith, RN- CRNA`` reads as it always has, with ``RN-`` as the
given name and ``Jane Smith`` as the family. Behind a single word
(``Smith, RN - CRNA``) nothing is split, and before the comma the
hyphen is a word too, so it never reaches a hyphenated surname written
with spaces (``Smith - Jones``).

Declaring another separator
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``extra_suffix_delimiters`` handles sources that separate post-nominals
with something else. Undeclared, the separator is a word. Since 2.4
such a name still parses when a credential opens the part after the
comma, because that makes the whole part the suffix, but the separator
stays in the suffix as written. Declared, it splits the suffix into
groups the way a comma does:

.. doctest::

    >>> name = parse("Jane Smith, RN | CRNA")
    >>> name.given, name.family, name.suffix
    ('Jane', 'Smith', 'RN | CRNA')
    >>> policy = Policy(extra_suffix_delimiters=frozenset({" | "}))
    >>> name = Parser(policy=policy).parse("Jane Smith, RN | CRNA")
    >>> name.given, name.family, name.suffix
    ('Jane', 'Smith', 'RN, CRNA')

A declared separator also counts glued to a word, as the semicolon
does, and stays in the suffix as written there: declaring ``" - "``
reads ``Jane Smith, RN- CRNA`` as given ``Jane``, family ``Smith``.

Through 2.3 the undeclared reading of ``Jane Smith, RN - CRNA`` was
given ``RN``, family ``Jane Smith`` and suffix ``CRNA``, so the
delimiter was the only way to get the name right, and through 2.6 it
was the only way to split the suffix.

Credentials written joined or split
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A hyphen or a slash written between two credentials with no space needs
no declaring when every part is a listed credential, because the word
then reads as one credential (since 2.7). A part that may also be a
name, such as ``MA``, counts where a part that is not a name stands
beside it (since 3.0). Parts that may all be names keep the word a name
word, since a hyphen also joins surnames, unless the word is written in
capitals, which :ref:`all-caps-credentials` reads on its own terms:

.. doctest::

    >>> joined = parse("Jane Smith, RN/CRNA")
    >>> joined.given, joined.family, joined.suffix
    ('Jane', 'Smith', 'RN/CRNA')
    >>> joined = parse("Jane Smith, MA/PhD")
    >>> joined.given, joined.family, joined.suffix
    ('Jane', 'Smith', 'MA/PhD')
    >>> joined = parse("Jane Smith, MA/Mba")
    >>> joined.given, joined.family
    ('MA/Mba', 'Jane Smith')

A credential written with a space inside it, such as ``Pharm D``, is
read as one credential too (since 2.7), where the name has words to
spare in front of it:

.. doctest::

    >>> parse("John Smith, Pharm D").suffix
    'Pharm D'

.. _unlisted-credentials:

Credentials the vocabulary doesn't list
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

No suffix list holds every post-nominal, so two ``Policy`` fields, both
new in 2.4, read
an unlisted word as a credential from how it is written: in periods
(``X.Y.Z.``), or in capitals (``XYZ``). The writing cannot settle it
alone, because a surname can be written either way, so both fields
also decide by position: the word has to stand behind a name that can
spare it.

Both fields share one exception. Two letters alone right after a comma
are how a person's initials are written, and the words before the comma
may be one surname of two words, so ``"García Márquez, G.J."`` and
``"García Márquez, MJ"`` keep given ``G.J.`` and ``MJ``. The dotted
spelling reports the bare reading as a fork; the capitals do not.

The exception gives way to evidence that the letters are a credential:
an unambiguous post-nominal in front of them that is not also a title,
or another unlisted dotted or all-caps word beside them that its own
field reads as a credential. A title in front of them says the
opposite:

.. doctest::

    >>> parse("John Smith, PhD X.Y.").suffix
    'PhD X.Y.'
    >>> parse("John Smith, PhD MJ").suffix
    'PhD MJ'
    >>> parse("García Márquez, MJ XYZ").suffix
    'MJ XYZ'
    >>> cred = parse("García Márquez, Ms G.J.")
    >>> cred.title, cred.given
    ('Ms', 'G.J.')

.. _dotted-credentials:

Dotted acronyms
^^^^^^^^^^^^^^^

``unlisted_dotted_suffixes`` is on by default. It reads a token of two
or more period-separated chunks as a credential at the end of a name,
right after a comma behind two or more name words, at the end of the
given part after a family comma, and at the end of a maiden marker's
clause. Case is irrelevant; the periods are the signal.
With nothing to spare in front of it, the word stays a name. At the end
of a name, given part or clause, either reading reports the fork as a
``suffix-or-name`` ambiguity, so a record that reads wrong can still be
found; right after a comma behind a full name, the credential reading
is taken silently:

.. doctest::

    >>> cred = parse("John Smith X.Y.Z.")
    >>> cred.family, cred.suffix
    ('Smith', 'X.Y.Z.')
    >>> parse("Jack X.Y.Z.").family
    'X.Y.Z.'
    >>> cred = parse("Doe, John X.Y.Z.")
    >>> cred.given, cred.suffix
    ('John', 'X.Y.Z.')
    >>> parse("Doe, X.Y.Z.").given
    'X.Y.Z.'
    >>> cred = parse("Jane Doe nee Smith X.Y.Z.")
    >>> cred.maiden, cred.suffix
    ('Smith', 'X.Y.Z.')
    >>> cred = parse("John Smith, X.Y.Z.")
    >>> cred.suffix, cred.ambiguities
    ('X.Y.Z.', ())

Five things are not this shape. A token the vocabulary already knows
(``M.A.``, ``Ph.D.``) is read by the vocabulary. A single trailing
period is how any word is abbreviated, so ``"John Smith Xyz."`` keeps
family ``Xyz.``. Every chunk must be alphabetic, so a digit anywhere
refuses it (``"John Smith 1.4"`` keeps family ``1.4``). A script
with no period abbreviations of its own refuses it too
(``"John Smith 田.中."`` keeps family ``田.中.``). And two single
letters, each with its period, are how initials are written, and how
some surnames are, such as the Nepali ``B.K.``: in a script with
capitals they stay a name word wherever they end a name, given part or
clause, and still report the fork, while three letters or more are a
credential as before. Right after a comma they are the exception above:

.. doctest::

    >>> nepali = parse("Ram Bahadur B.K.")
    >>> nepali.middle, nepali.family
    ('Bahadur', 'B.K.')
    >>> parse("Doe, John B.K.").middle
    'B.K.'

Setting the field to ``False`` reads such a token as name material
everywhere, and still reports the fork. It does not bring back the
pre-2.4 reading of a chunk that is one ASCII character, a roman numeral
or the digit ``2``, as a credential. That reading was retired outright,
not put behind this switch, so ``"Jack X.Y.I."`` and the version string
``"John Smith 1.4.2"`` keep their last word as the family name either
way:

.. doctest::

    >>> dotted_off = Parser(policy=Policy(unlisted_dotted_suffixes=False))
    >>> dotted_off.parse("John Smith X.Y.Z.").family
    'X.Y.Z.'
    >>> dotted_off.parse("Jane Doe nee Smith X.Y.Z.").maiden
    'Smith X.Y.Z.'

.. _all-caps-credentials:

All-caps words
^^^^^^^^^^^^^^

``unlisted_caps_suffixes`` reads an unlisted word of two or more
capital letters, with no period in it, and since 2.7 one of capitals
joined by a hyphen or a slash (``PU-PH``, ``MS-OMPT``) with a part of
two or more letters. Its value is a
:class:`~nameparser.CapsSuffixes`, because where capitals mean a
credential depends on a second convention: many records write the
SURNAME in capitals (``"Jean DUPONT"``, ``"DUPONT, Jean"``).

The capitals only mean something against a name that does not use
them. The name must hold a word of its own with a capital and a
lowercase last letter (``Smith``, ``DiCaprio``) that the vocabulary
does not claim as a title, particle or credential. A record written
wholly in capitals, or wholly in lowercase, keeps every word a name
word.

``AFTER_COMMA`` (the default)
"""""""""""""""""""""""""""""

``CapsSuffixes.AFTER_COMMA`` reads the word only in the
part right after a comma with two or more name words before it. The
all-caps surname convention never writes capitals there:

.. doctest::

    >>> from nameparser import CapsSuffixes
    >>> cred = parse("John Smith, XYZ")
    >>> cred.family, cred.suffix
    ('Smith', 'XYZ')
    >>> parse("Smith, XYZ").given
    'XYZ'
    >>> parse("JOHN SMITH, XYZ").given
    'XYZ'
    >>> cred = parse("John Smith, PU-PH")
    >>> cred.family, cred.suffix
    ('Smith', 'PU-PH')

``EVERYWHERE``
""""""""""""""

``CapsSuffixes.EVERYWHERE`` also reads the end of a name, the given
part's last word after a family comma, and the word ending a maiden
marker's clause. Those are the places an all-caps surname IS written,
which is why it is not the default:

.. doctest::

    >>> caps_everywhere = Parser(
    ...     policy=Policy(unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE))
    >>> caps_everywhere.parse("John Smith XYZ").suffix
    'XYZ'
    >>> caps_everywhere.parse("Doe, John XYZ").suffix
    'XYZ'
    >>> cred = caps_everywhere.parse("Jane Doe nee Smith XYZ")
    >>> cred.maiden, cred.suffix
    ('Smith', 'XYZ')
    >>> cred = caps_everywhere.parse("Jean Pierre DUPONT")
    >>> cred.family, cred.suffix
    ('Pierre', 'DUPONT')

``OFF``
"""""""

``CapsSuffixes.OFF`` reads none of them and reports nothing, as 2.3
did. It is the way to keep a given name written in capitals after a
two-word surname, which the default reads as a credential:

.. doctest::

    >>> parse("García Márquez, GABRIEL").suffix
    'GABRIEL'
    >>> caps_off = Parser(
    ...     policy=Policy(unlisted_caps_suffixes=CapsSuffixes.OFF))
    >>> caps_off.parse("García Márquez, GABRIEL").given
    'GABRIEL'

.. _strip-flags:

Keeping emoji and control characters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The strip flags keep characters the parser removes by default. Note
what happens to an emoji you keep — it becomes a token like any other,
and lands in the middle name:

.. doctest::

    >>> str(parse("Sam 😊 Smith"))                      # stripped by default
    'Sam Smith'
    >>> kept = Parser(policy=Policy(strip_emoji=False)).parse("Sam 😊 Smith")
    >>> str(kept), kept.middle
    ('Sam 😊 Smith', '😊')

``strip_bidi=False`` does the same for invisible bidirectional control
characters, which is occasionally what you want when round-tripping
right-to-left text verbatim.

.. _rendering-arguments:

Presentation: rendering arguments
----------------------------------

Once a name is parsed, how it's displayed is a separate decision made
at the point of output, not baked into the parse. Three methods on
:class:`~nameparser.ParsedName` cover it — see :doc:`modules` for full
signatures:

* :meth:`~nameparser.ParsedName.render` fills a format spec from the
  seven role fields and the views derived from them (``family_base``,
  ``generation``, ``credentials`` and the rest). With no spec, as
  ``str()`` calls it, it lays the name out in the order it was read in
  (since 3.0).
* :meth:`~nameparser.ParsedName.initials` is the same idea narrowed to
  first letters, with its own ``delimiter``/``separator`` arguments.
* :meth:`~nameparser.ParsedName.capitalized` returns a new, case-fixed
  :class:`~nameparser.ParsedName` instead of a string. It only touches
  a name whose words are written in a single case (all lower, all
  upper) unless you pass ``force=True`` — mixed case is left alone by
  default on the assumption that someone already capitalized it on
  purpose. The suffixes don't count toward that: ``III`` or ``PhD``
  written the usual way says nothing about how the name was cased.
  A suffix written in more than one case is the writer's spelling
  and is kept as written (``john smith EdD`` gives ``John Smith
  EdD``) unless you pass ``force=True``.

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.render("{family}, {given} {middle}")
    'de la Vega, Juan Q. Xavier'
    >>> name.initials(spec="{given}{middle}{family}", delimiter="", separator="")
    'JQXV'
    >>> str(parse("DR. JUAN DE LA VEGA").capitalized())
    'Dr. Juan de la Vega'
    >>> str(parse("JuAn DE LA vEGA").capitalized())
    'JuAn DE LA vEGA'
    >>> str(parse("JuAn DE LA vEGA").capitalized(force=True))
    'Juan de la Vega'
    >>> str(parse("juan garcia III").capitalized())
    'Juan Garcia III'

Looking for v1's ``string_format``? It's the ``render(spec)`` argument
now — pass your own format string per call instead of setting it once
on a shared config object.

A spec chooses what the output is *for*. The default is written for
display and does not survive a reparse — it parenthesizes the maiden
name, which reads back as a nickname. When the rendered string will be
parsed again, spell the marker out (``née {maiden}``) so the field
round-trips; see :ref:`the round-trip note in the tour <maiden-roundtrip>`.

Sharing a configured parser
----------------------------

A :class:`~nameparser.Parser` is a frozen value, so the way to share
one configuration across a codebase is the same way you'd share any
other constant: build it once at module level and import it wherever
you parse.

.. code-block:: python

    # myapp/names.py
    from nameparser import Lexicon, Parser, Policy

    lex = Lexicon.default().remove("dean", kind="given")
    policy = Policy(strip_emoji=False)
    parser = Parser(lexicon=lex, policy=policy)

    # elsewhere
    from myapp.names import parser
    name = parser.parse(raw_name)

Because :class:`~nameparser.Parser` and its ``lexicon``/``policy`` are
immutable and hashable, ``parser`` is safe to import and call from
multiple threads with no locking — there is no shared mutable state to
protect.
