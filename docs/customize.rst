Customizing the parser
=======================

When the defaults misread your data, try these in order, each a
smaller and more specific change than the one before:

#. **Let the data choose.** If you have a list of names from one
   source, :meth:`Parser.suggest() <nameparser.Parser.suggest>` reads
   the order it is written in, a patronymic rule, whether letters
   ending a name are its family name and whether family names are
   written in capitals, and returns a parser set for them
   (:doc:`suggest`).
#. **Choose the language.** If you know the data's language, a locale
   pack (:doc:`locales`) reads that language's words and conventions,
   such as Spanish double surnames or Russian patronymics. Call
   ``suggest`` on the pack's parser to have both.
#. **Set a behavior.** A :class:`~nameparser.Policy` field changes how
   positions and punctuation are read, the same for every word:
   :doc:`policy` lists them.
#. **Edit the vocabulary.** A :class:`~nameparser.Lexicon` edit, the
   subject of this page, changes how one word is read.

Every piece of nameparser configuration sorts into one of three places
by asking what it varies with: vocabulary varies by **language**
(:class:`~nameparser.Lexicon`), behavior varies by **data source or
application** (:class:`~nameparser.Policy`), and presentation varies by
**output destination** (a rendering argument). See :doc:`concepts` for
why the split is drawn there.

.. _vocabulary-lexicon:

Vocabulary: Lexicon
--------------------

When your data is in a known language, choose the language before
editing words one at a time: a choice of languages
(:ref:`choosing-languages`) makes that language's reading win on a word
it lists as vocabulary (Portuguese ``do`` the particle over English
``DO`` the credential), and a strict choice (:ref:`strict-choice`) also
drops the readings other languages' files hold of words written in
Latin letters, keeping the shared ``mul`` file's. The edits below are for what a choice leaves open, and
for data whose language you cannot declare, which the default
vocabulary, reading every language at once, already serves.

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

Both calls return a new :class:`~nameparser.Lexicon`, the one you
started from (here, ``Lexicon.default()``) never being mutated.

.. _adding-a-word:

Adding a word
^^^^^^^^^^^^^

:meth:`~nameparser.Lexicon.add` takes the words and a ``kind``, one of
those `Kinds and properties`_ lists. A credential the defaults do not
list is one reading per word:

.. doctest::

    >>> parse("John Smith LEED AP").suffix
    ''
    >>> lex = Lexicon.default().add("leed", "ap", kind="credential")
    >>> Parser(lexicon=lex).parse("John Smith LEED AP").suffix
    'LEED AP'

A surname particle is added the same way. The defaults leave out the
Dutch ``in`` of ``in 't Veld``, which as a default would take a middle
name spelled like it into the surname of names in every language; add
it when your data is Dutch:

.. doctest::

    >>> parse("Marieke in 't Veld").middle, parse("Marieke in 't Veld").family
    ('in', "'t Veld")
    >>> dutch_in = Lexicon.default().add("in", kind="preposition")
    >>> Parser(lexicon=dutch_in).parse("Marieke in 't Veld").family
    "in 't Veld"
    >>> Parser(lexicon=dutch_in).parse("Park In Hwan").family
    'In Hwan'

The last line is the cost: an edit applies to every name the parser
reads. A particle added this way holds no ``given`` reading, so
opening a name with a word behind it, it starts the surname rather
than standing as the given name (`Particles that are also given
names`_).

Where a word already holds a reading of the kind added, ``add`` updates
that reading in every file holding it (`Updating a reading the word
already holds`_); otherwise it adds a reading of your own.

Two lists are not readings, and are joined to a lexicon rather than
added to it: ``surnames``, which divides an unspaced name
(:ref:`east-asian-defaults`), and ``given_names``, which the
two-family-name switch reads (:ref:`two-family-names`).

Removing a word
^^^^^^^^^^^^^^^

:meth:`~nameparser.Lexicon.remove` takes the words and, optionally, a
kind. What it takes out depends on what you pass:

- **No kind**: every reading of the word.
- **A kind** (``kind="given"``, as in the first example): the word's
  readings of that kind.
- **A category** (``kind="title"``, ``kind="name"``): every reading of
  the word in that category, whatever its kind.
- **A kind or a category, no words, and** ``every=True``: every word's
  readings of it, as ``remove(kind="title", every=True)`` does
  (:ref:`title-detection-off`). A removal that leaves a word the
  lexicon refuses raises: ``remove(kind="given", every=True)`` does, a
  bound given name that is also a particle needing its ``given``
  reading.

``professor`` holds an ``academic`` reading, and ``"title"`` here names
its category:

.. doctest::

    >>> lean = Lexicon.default().remove("professor", kind="title")
    >>> Parser(lexicon=lean).parse("Professor Robert Johns").title
    ''

Seeing what the vocabulary says about a word
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:meth:`~nameparser.Lexicon.readings_of` answers what a word may be read
as in a lexicon. Each :class:`~nameparser.LexiconReading` gives its
kind, its category, its properties and the shipped files that hold it,
named by language, which a reading you added leaves empty:

.. doctest::

    >>> for van_reading in Lexicon.default().readings_of("van"):
    ...     print(van_reading.kind, van_reading.category, van_reading.languages)
    preposition particle ('nl',)
    given name ('nl',)
    >>> dutch_in.readings_of("in")[0].languages
    ()

:meth:`~nameparser.Lexicon.words` goes the other way: it lists the
words holding a reading of a kind or a category, and of a property
where you pass one. The examples under :ref:`title-detection-off` use
it too:

.. doctest::

    >>> Lexicon.default().words(kind="conjunction", may_be_initial=True)
    ('e', 'i')

Both say what a word *may* be read as. Whether a parse read a word that
way is :attr:`Token.reading <nameparser.Token.reading>`'s question
(:ref:`reading-taken`).

Coming from 2.x
^^^^^^^^^^^^^^^

The 2.x set fields (``titles``, ``suffix_acronyms``,
``particles_ambiguous``, ...) are internal since 3.0, compiled from the
readings: ``add(titles=...)``, ``Lexicon(titles=...)`` and
``lexicon.titles`` each raise, the error naming the calls that configure
the same words. The modules that exposed the default word lists as
constants in 2.x (``nameparser.config.titles``, ``particles``,
``suffixes`` and the rest) are gone in 3.0, ``words`` and
``readings_of`` answering for them, and the Korean surname list,
``nameparser.config.surnames`` through 2.x and private in 3.0, is the
default lexicon's ``surnames``: ``Lexicon.default().surnames``.
:doc:`migrate` has the table of fields and the call or comprehension
for each constant.

Kinds and properties
~~~~~~~~~~~~~~~~~~~~~

A kind belongs to a category, which decides what the reading does:

.. list-table::
   :header-rows: 1
   :widths: 14 46 40

   * - Category
     - What a reading of it does
     - Kinds
   * - title
     - The word is a title in front of the name, and written with its
       period at the end of one (:ref:`trailing-titles`). A ``given``
       reading on the word limits both (`Name readings`_).
     - ``title``, ``salutation``, ``style``, ``academic``, ``religious``,
       ``nobility``, ``military``, ``office``, ``occupation``,
       ``kinship``, ``modifier``
   * - suffix
     - The word is a suffix at the end of the name or after a comma.
     - ``suffix``, ``generation``, ``agnomen``, ``credential``,
       ``honorific``, ``professional_honorific``, ``status``,
       ``courtesy``
   * - particle
     - The word joins the family name that follows it (``de la Vega``).
     - ``particle``, ``preposition``, ``article``, ``patronymic``,
       ``teknonymic``, ``clan``, ``rank``, ``saint``, ``alias``
   * - conjunction
     - The word joins the name parts, or the titles, on either side of
       it (``Garcia y Lopez``, ``Mr. and Mrs.``).
     - ``conjunction``
   * - bound_given
     - The word joins the word after it into one given name
       (`Bound given names`_).
     - ``bound_given``
   * - bound_second
     - The word joins the word before it into one name (``عز الدين``),
       added in 3.2 (`Bound given names`_).
     - ``bound_second``
   * - relation
     - The name after the word is the maiden name (``née``), or a
       second name the person is known by, read as the nickname
       (``@``, ``urf``; added in 3.2, `Alias markers`_).
     - ``birth_marker``, ``alias_marker``
   * - name
     - The word is borne as a name. With no property it moves a parse
       only beside another reading of the word (`Name readings`_).
     - ``given``, ``family``
   * - familiar
     - The word is a short given name standing for longer ones, read by
       name matching alone (`Familiar forms`_).
     - ``familiar``
   * - spelling
     - The word is another spelling of a given name, read by name
       matching alone (`Alternate spellings and listed spellings`_).
     - ``spelling``

For title, suffix, particle and conjunction the category's own name is
also a kind, for a word you have no finer kind for. A finer kind
classifies the word, and some rules read it. Among them:

- A title's kind is what another title's ``attaches`` names, and
  ``modifier`` and ``style`` make a title phrase with the title after
  them (:ref:`titles-also-given-names`).
- ``generation``, ``agnomen`` and ``credential`` are the suffix kinds a
  name reading on the word makes ambiguous (:ref:`ambiguous-words`),
  as it does a suffix of any kind written ``acronym=True``; a suffix
  word of another kind stays a suffix beside one. An ``agnomen`` needs
  that name reading.
- A suffix written as a word shows in the ``generation`` view as a
  ``generation`` or an ``agnomen`` and in ``honorifics`` as an
  ``honorific`` or a ``professional_honorific``; any other suffix, and
  every acronym, shows in ``credentials``. A ``patronymic`` particle
  fills the ``patronymic`` view (:ref:`aggregate-views`).
- ``saint`` and ``rank`` are written with a capital by case repair
  (:ref:`case-exceptions`).

A reading takes the properties of its category, written as keyword
arguments to ``add``:

.. list-table::
   :header-rows: 1
   :widths: 24 16 60

   * - Property
     - On
     - What it does
   * - ``addresses="given"``
     - title
     - The lone name after the title is a given name, as after ``Sir``
       (`Phrases`_).
   * - ``after_given=True``
     - title
     - Written bare at the end of the given names after a family comma,
       the word is the title, as ``Mrs`` is in ``Doe, Jane Mrs``.
   * - ``abbreviation=True``
     - title
     - On a title that is also a given name: written with its period
       at the end of the name, it is the title (``SMITH, JOHN B. MAJ.``).
   * - ``attaches=[...]``
     - title
     - The title kinds, or title words, it makes a two-word phrase with
       (:ref:`titles-also-given-names`).
   * - ``dotted=True``
     - title
     - The title is also read from single letters joined by full stops,
       before another title (``U.S. District Judge``).
   * - ``attached="before"``
     - title
     - The title is split off the start of a name it is glued to
       (Thai ``นายสมชาย``), never in a name written wholly in ASCII.
   * - ``attached="after"``
     - suffix
     - The word is split off the end of a name it is glued to
       (``田中さん``), never in a name written wholly in ASCII.
   * - ``acronym=...``
     - suffix
     - True, a ``credential``'s unwritten value: matched with every
       period removed, so ``M.D.`` is ``md``. False: a suffix written as
       a word.
   * - ``title_case_is_name=True``
     - suffix
     - On a ``generation``, an ``agnomen`` or a ``credential`` written
       as a word, where the word is also a name: Title case reads the
       name, lower case the suffix (`Generation words that are also
       surnames`_).
   * - ``capital_opening=True``
     - particle
     - Case repair writes the particle with a capital where it opens
       the family name (``Levon Ter Petrosyan``).
   * - ``may_be_initial=True``
     - conjunction
     - A single letter reads as an initial in a name written wholly in
       one case (:ref:`connectives-also-initials`).
   * - ``completed_by=[...]``
     - bound_given
     - The words it joins past the first name word
       (`Bound given names`_).
   * - ``completes=[...]``
     - bound_second
     - The only words it joins behind (`Bound given names`_).
   * - ``after_particle=True``
     - ``given``
     - Behind a particle the word completes a given name, so
       ``María del Carmen García`` reads middle ``del Carmen``
       (:ref:`two-given-names`).
   * - ``shared=True``
     - ``given``, ``family``
     - A name a community shares (Sikh ``Kaur``), which the
       two-family-name and two-given-name switches leave a middle name
       (:ref:`two-family-names`).
   * - ``short_for=[...]``
     - familiar
     - The longer given names the word stands for (`Familiar forms`_).
   * - ``spelling_of=[...]``
     - spelling
     - The given names the word is another spelling of (`Alternate
       spellings and listed spellings`_).
   * - ``same_as=...``
     - every kind but ``familiar`` and ``spelling``
     - The word, or words, this one is a spelling of (`Alternate
       spellings and listed spellings`_).

``nameparser/vocab/README.md`` in the repository is the full reference
for each kind and property.

Updating a reading the word already holds
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``add`` on a reading the word already holds updates only the
properties you pass (a ``familiar`` or a ``spelling`` reading extends
instead, `Familiar forms`_). A property given its unwritten value (``None``,
``False``) is removed; ``acronym`` is unwritten-true on a
``credential`` alone. Two things are not properties: whether a reading
is on (a caller's always is) and its case mask (:ref:`case-exceptions`).

So ``add("md", kind="given")`` keeps the shipped reading, ``md`` being
Muhammad written short since 3.1, and changes nothing. Through 3.0.1
the same call gave ``md`` a plain given reading, which made the
credential ``MD`` one read only where the name has words to spare;
that reading now takes ``same_as=None``:

.. doctest::

    >>> plain_md = Parser(lexicon=Lexicon.default().add(
    ...     "md", kind="given", same_as=None))
    >>> plain_md.parse("John Smith Md").family
    'Md'
    >>> Parser().parse("John Smith Md").suffix
    'Md'

.. _customize-md-title:

Keeping Md. a title
^^^^^^^^^^^^^^^^^^^

Through 3.0.1 a leading ``Md.`` read as a title, and ``Md`` after a
family comma as the credential; through 3.1, ``MD`` inside a name
written in capitals read as the credential, taking the words behind
it. To keep those readings, remove the given reading; the name match
then no longer links ``Md`` to the long spellings of Muhammad:

.. doctest::

    >>> md_title = Parser(lexicon=Lexicon.default().remove("md", kind="given"))
    >>> md_title.parse("Md. Rahman").title
    'Md.'
    >>> md_title.parse("Rahman, Md").suffix
    'Md'
    >>> md_title.parse("SITI NORA MD YUSRI").suffix
    'MD YUSRI'

Name readings
^^^^^^^^^^^^^

A **name** reading beside another reading is what makes a word
ambiguous, as the vocabulary files mark it: a title with a ``given``
reading is a title only inside a phrase, a particle with one may be a
given name, and a credential or a generation word with a name reading
is read as the suffix only where the writing or the count says so
(:ref:`ambiguous-words`). So ``add("guru", kind="given")``
makes ``Guru`` a title only inside a phrase, and
``remove("van", kind="given")`` makes a ``van`` that opens a name, with
a word behind it, part of the surname rather than the given name.

The period does less for a title holding a ``given`` reading than for
any other. In front of a name written without a comma the word with
its period is still a title, by its shape (``Dean. John Smith``). At
the end of a name it is one only where its reading carries
``abbreviation``: ``John Smith Maj.`` reads title ``Maj.``, where
``John Smith Dean.`` reads family ``Dean.``.

Familiar forms
^^^^^^^^^^^^^^

A ``familiar`` reading is a short given name standing for the longer
ones its ``short_for`` lists (``max`` for Maximilian). No parse reads
it: name matching reads it as the opt-in ``familiar-form``
(:ref:`matching-familiar-forms`), and
:ref:`matching-editing-familiar-forms` has the recipes for adding and
removing one. Three things are particular to it, and to a ``spelling``
reading:

- **An add extends.** ``add("max", kind="familiar",
  short_for=["maxine"])`` adds to the longer names the shipped
  vocabulary lists for ``max`` (Maximilian, Maxwell and others), in a
  reading of your own that names no file, where an add of a kind
  other than these two that the word holds updates that reading.
- **A pair is removed from either name.** It is stored on the word
  whose reading lists the other, as ``readings_of("max")`` shows:
  ``remove("max", kind="familiar", short_for=["maximilian"])`` cuts
  ``Max`` / ``Maximilian``, either name first, and
  ``remove("maximilian", kind="familiar")`` drops every pair naming
  that word, whichever name holds it.
- **It names other words.** A familiar reading needs at least one name
  in ``short_for``, and none may be the word itself.

Alternate spellings and listed spellings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A ``spelling`` reading is a given name written another way (``olha``
for Olga), its ``spelling_of`` listing the names. It is edited as a
familiar form is, and name matching reads it as the opt-in
``alternate-spelling`` (:ref:`matching-alternate-spellings`).

``same_as="..."``, accepted on a reading of every kind but ``familiar``
and ``spelling``, names the word this one is a spelling of (``jnr`` is
``jr``), or a list of them where it is a spelling of several
(``same_as=["muhammad", "mohammad"]``). Name matching reads two words
whose ``same_as`` links reach a common word as a ``listed-spelling``
and gives them the same grouping key
(:ref:`matching-listed-spellings`). ``same_as`` moves no word between kinds, save on a ``given``
reading, where it also marks the word as a given name written short
(``chas`` is ``charles``), so ``Chas. Smith`` reads given ``Chas.``
rather than a title.

Two rules follow for a given name written short:

- **One that is also a given name of its own** in the vocabulary
  (``jo``, José written short and the name Jo) counts as a listed
  spelling only where it is written with its period. That rule reads
  the vocabulary as you edited it: your ``same_as`` on a word applies
  to its given readings, so the word then has no plain reading and its
  link counts written bare (``add("dean", kind="given",
  same_as="deanna")`` makes ``Dean Smith`` and ``Deanna Smith`` a
  listed spelling), and you cannot currently mark a word of your own
  as a name of its own.
- **It is no name a credential of the same spelling clashes with.**
  Where the word is also a credential read only where the name has
  words to spare because it may be a name, the given name written
  short takes that doubt away, so with ``add("jd", kind="given",
  same_as="zachary")``, ``Smith Jd`` ends in the credential ``Jd``
  rather than the family name.

Phrases
^^^^^^^

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

Alias markers
^^^^^^^^^^^^^

An ``alias_marker`` reading makes a word announce a second name the
person is known by, which is read as the nickname, the marker dropped.
``@`` written as a word of its own and ``urf`` are read so by default.
The English ``alias`` and ``aka`` ship turned off, because each is a
given name or a surname more often than a marker (``Aka`` is a Turkish
and an Ivorian surname). If your records write them as markers, add
them:

.. doctest::

    >>> fec = Parser(lexicon=Lexicon.default().add(
    ...     "aka", "alias", kind="alias_marker"))
    >>> boscia = fec.parse("BOSCIA, FRANK AKA FRANCIS")
    >>> boscia.given, boscia.nickname
    ('FRANK', 'FRANCIS')
    >>> parse("BOSCIA, FRANK AKA FRANCIS").middle
    'AKA FRANCIS'

The alias runs to a patronymic particle (``bin``, ``a/l``), another
marker or a comma, and otherwise to the end of the name, less any
trailing suffixes and titles. So two words after the marker are both taken, which
is right for a whole second name and wrong for a one-word alias before
the family name.

.. _title-detection-off:

Turning title detection off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To stop the vocabulary reading any word as a title, remove every title
reading:

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

``every=True`` with a kind and no words takes out every word's readings
of it, and the category ``"title"`` matches every title kind, so every
title reading goes at once. A call with no words and no ``every``
raises, so an empty ``remove(*words, kind=...)`` never does this.

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
in plain capitals.

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

Where a name reading is what marks the word, a choice of languages can
settle it only where one of its two readings sits in another
language's file:
:ref:`choosing-languages` and :ref:`strict-choice` say which of those
readings a plain and a strict choice switch off, and the ``DO`` example
under `Mark a word, or leave it out`_ shows one settled. Where the
chosen language's own file, or the shared ``mul`` file, holds both
readings, no choice settles the word. English lists ``ma`` as a
credential and as a surname, so even a strict English choice reads
``JOHN SMITH MA`` by the count and reports it:

.. doctest::

    >>> from nameparser import Locale, parser_for
    >>> english = Locale(code="en", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"en"}))
    >>> english_ma = parser_for(english, strict=True).parse("JOHN SMITH MA")
    >>> english_ma.suffix, english_ma.ambiguities
    ('MA', (Ambiguity('suffix-or-name': 'MA'),))

Dutch holds neither reading of ``ma``, so a strict Dutch choice drops
both: it reads the same name family ``MA`` and reports nothing. The
recipes in this section are the way to settle the rest. A one-letter
connective is different, its language's choice settling it (`One-letter
connectives that are also initials`_).

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
    >>> parse("John Smith Ma").family
    'Ma'

A bare marked acronym with no comma right before it and no brackets
around it is read by the first of these signals that applies (where the parse reads
it by the count or by a Title-case lean, it reports a
``suffix-or-name`` ambiguity, :ref:`credentials-also-surnames`):

#. **ALL CAPITALS** in a mixed-case name leans to the credential: it is
   a suffix even with no words to spare (``"Jack MA"``). The capitals
   settle it as the periods do, so the acronym reports no
   ``suffix-or-name`` ambiguity, and a word after it in the given part after a family
   comma reads as part of the suffix (``"Smith, John MA Jones"`` gives
   suffix ``MA Jones``).
#. **Title-case** in a mixed-case name leans to the surname: it stays
   the family name even WITH words to spare (``"John Smith Ma"``).
#. **No signal** — all lowercase in a mixed-case name, or any spelling
   in a name written wholly in one case — falls back to the count: a
   suffix with two or more words before it, not counting a title or a
   nickname (``"John Smith ma"``), the family name otherwise
   (``"JACK MA"``).

**Right after a comma** the count of name words before the comma decides
FIRST, and the case is read only where the count leaves the word a
name. ``"John Smith, Ba"`` reads suffix ``Ba`` on the count alone, and
``"Smith, BA"`` reads suffix ``BA`` on the capitals lean. What still
reads as the given name is ``"Smith, Ba"`` (one word, and Title-case
has no credential lean) and ``"smith, ba"`` (one word, one case, no
lean at all).

**In brackets after the name**, the capitals in a mixed-case name
settle it as the credential too, and so does a period inside the word:
``"John Smith (BA)"`` and ``"John Smith (B.A)"`` give suffix ``BA`` and
``B.A``. Any other spelling there, and any spelling inside the name,
falls through to nickname parsing (``"John Smith (Ba)"``,
``"Jeffrey (JD) Bricken"``), reported as a ``suffix-or-nickname``
ambiguity.

Malay names and bt
^^^^^^^^^^^^^^^^^^

``bt`` is listed as a credential, Baronet (``Sir John Smith Bt``),
and Malay names write it for *binti*, between a woman's name and her
father's. Written any way but in Title case, the credential reading
takes the father's name into the suffix. A caller reading Malay names
removes the reading:

.. doctest::

    >>> parse("Nur Aina bt Rosli").suffix
    'bt Rosli'
    >>> malay = Parser(lexicon=Lexicon.default().remove("bt", kind="credential"))
    >>> aina = malay.parse("Nur Aina bt Rosli")
    >>> aina.suffix, aina.family
    ('', 'Rosli')

Removing it costs a baronet his post-nominal: ``Sir John Smith Bt``
then reads family ``Bt``, and ``Sir John Smith, Bt`` reads given
``Bt``, the name before the comma the family. The default keeps the
reading because ``bt`` is rare on the lists measured, a Malaysian one
included (:issue:`1467`), and ``Bt`` written in Title case reads as a
name word already (``Nur Aina Bt Rosli``).

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
  specialized beside a common surname. The default vocabulary leaves
  out ``rai`` and ``cha`` for that reason; a caller who needs one adds
  it back with ``Lexicon.default().add("cha", kind="credential")``.

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

A ``given`` reading is the same idea for surname particles. It shows
in what a particle standing alone at the front of a name, with a word
behind it, does:

- **A particle holding a** ``given`` **reading** may also be a given
  name, so a leading one is a decision to take. By default it is the
  given name; which field it lands in is ``name_order``'s question
  (:ref:`order-vocabulary-first`).
- **A particle holding none** cannot be the given name there, so
  there is nothing to decide. It starts the surname under every
  ``name_order``, because a word that can never be a given name leaves
  the order nothing to decide, and by default it pulls the rest of the
  name into the surname and leaves no given name at all.

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
``given`` reading: a leading ``van`` with a word behind it is then no
decision at all, so no ambiguity is recorded and it becomes part of
the surname — under any ``name_order``, since that is what taking the
word out asserted (``Van`` standing alone is still a given name):

.. doctest::

    >>> lex = Lexicon.default().remove("van", kind="given")
    >>> Parser(lexicon=lex).parse("van Gogh").family
    'van Gogh'

For particles the default runs the other way from credentials: a
particle that is not borne as a given name holds no ``given`` reading,
which is where ``mc`` and ``ste`` were moved (:issue:`360`).

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
For Portuguese ``e``, use the ``pt`` pack (``locales.PT_BR`` and
``locales.PT_PT`` read it the same way):

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

Past the first name word, a bound word joins a word its reading lists
in ``completed_by``, or, where its reading is written ``completes_any``,
any name word after it with no vocabulary reading and no initial's
shape. Arabic-script ``عبد``
lists the names of God and the devotional names it completes, so the
pair is one name wherever it stands. The Latin spellings name no word
after them and complete with any, ``abdul`` only in a name of four
words or more, titles and suffixes not counted (``long_names_only``),
its three-word names being split
both ways by the people who write them:

.. doctest::

    >>> parse("طارق عبد العزيز").family
    'عبد العزيز'
    >>> parse("Tariq Abdel Aziz").family
    'Abdel Aziz'
    >>> parse("Tariq Abdul Aziz").family
    'Aziz'

Where your names are Malaysian, which write a three-word ``X Abdul Y``
with the pair as the family, state ``abdul``'s reading without
``long_names_only``:

.. doctest::

    >>> lex = (Lexicon.default().remove("abdul", kind="bound_given")
    ...        .add("abdul", kind="bound_given", completes_any=True))
    >>> Parser(lexicon=lex).parse("Tariq Abdul Aziz").family
    'Abdul Aziz'

A ``bound_second`` reading (3.2) is the other end of such a pair: the
word written second, which joins the word before it. Arabic script
writes many given names as a word and ``الدين`` ("of the faith") or
``الله`` after it, the word before varying, so ``الدين`` and ``الله``
join any plain word before them, at the start of a name too, where the
pair is the given name. ``الغنى`` and ``الفقار`` are written
``completes=["ذو"]``, joining behind ``ذو`` alone; a word that lists
them joins behind those words only. A name of two name words keeps
them apart, as it keeps ``عبد الله``:

.. doctest::

    >>> noor = parse("نور الدين سامر حداد")
    >>> noor.given, noor.middle
    ('نور الدين', 'سامر')
    >>> parse("سامر عز الدين").family
    'عز الدين'
    >>> parse("عز الدين").given
    'عز'

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
  :class:`~nameparser.ParsedName` instead of a string.

``capitalized()`` decides what to touch by three rules:

- It only touches a name whose words are written in a single case (all
  lower, all upper) unless you pass ``force=True``. Mixed case is left
  alone by default on the assumption that someone already capitalized
  it on purpose.
- The suffixes don't count toward that: ``III`` or ``PhD`` written the
  usual way says nothing about how the name was cased.
- A suffix written in more than one case is the writer's spelling and
  is kept as written (``john smith EdD`` gives ``John Smith EdD``)
  unless you pass ``force=True``.

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
