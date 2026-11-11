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
       ``abbreviation=True``, ``attaches=[...]``, ``dotted=True``
   * - suffix
     - ``suffix``, ``generation``, ``agnomen``, ``credential``,
       ``honorific``, ``professional_honorific``, ``status``,
       ``courtesy``
     - ``acronym=...``, ``attached="after"``, ``title_case_is_name=True``
   * - particle
     - ``particle``, ``preposition``, ``article``, ``patronymic``,
       ``teknonymic``, ``clan``, ``rank``, ``saint``, ``alias``
     - ``capital_opening=True``
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
     - ``after_particle=True`` on ``given``; ``shared=True`` on either
   * - familiar
     - ``familiar``
     - ``short_for=[...]``, read by name matching alone

``nameparser/vocab/README.md`` in the repository says what each kind
and property means. A ``familiar`` reading is a short given name
standing for the longer ones its ``short_for`` lists (``max`` for
Maximilian): no parse reads it, and :ref:`name matching
<matching-names>` reads it as the opt-in ``familiar-form``.
``add("max", kind="familiar", short_for=["maxwell"])`` *extends* the
longer names the shipped vocabulary lists for ``max`` (Maksim, Maxim,
Maximilian), in a reading of your own that names no file, unlike an
add of any other kind the word holds, which updates that reading. A
pair lives on the word whose reading lists the other, as
``readings_of("max")`` shows: to cut ``Max`` / ``Maximilian``,
``remove("max", kind="familiar")`` and add back the names to keep,
``add("max", kind="familiar", short_for=["maksim", "maxim"])``. A
familiar reading needs at least one name, and none may be the word
itself.
``same_as="..."`` is accepted on a reading of every kind but
``familiar``: it names the word this one is a spelling of (``jnr`` is
``jr``), and :ref:`name matching <matching-names>` reads two words
whose ``same_as`` links reach a common word as a ``listed-spelling``
and gives them the same grouping key. A short form that is also a
given name of its own in the vocabulary (``jo``, José written short
and the name Jo) counts only where it is written with its period.
That rule reads the vocabulary as you edited it: your ``same_as`` on
a word applies to its given readings, so the word then has no plain
reading and its link counts written bare
(``add("dean", kind="given", same_as="deanna")`` makes ``Dean Smith``
and ``Deanna Smith`` a listed spelling), and you cannot currently mark
a word of your own as a name of its own. ``same_as`` moves no word
between kinds, save on a ``given`` reading, where it also marks the word as a given
name written short (``chas`` is ``charles``), so ``Chas. Smith`` reads
given ``Chas.`` rather than a title. A property given its unwritten
value (``None``, ``False``) is removed; ``acronym`` is unwritten-true
on a ``credential`` alone. Two things are not properties: whether a reading
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
