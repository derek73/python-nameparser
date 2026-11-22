Locale packs
============

A locale pack is an opt-in bundle of policy, vocabulary and a choice
of languages, each where a naming tradition needs it, for one specific
pattern: East Slavic patronymics, Turkic patronymic markers, the
titles and particles of one language, and so on. Packs apply only
when you ask for one by name.

- To see whether your names need a pack at all, read `What works
  without a pack`_.
- To turn one on, read `Using a pack`_, then find yours in `Shipped
  packs`_.
- To read the words of a language that has no pack, or only one
  language's words, read `Choosing languages`_.
- To write a pack for your own data, read `Creating your own Locale`_.

What works without a pack
--------------------------

Most international names need no pack at all. Besides Latin, the
default vocabulary covers Cyrillic, Greek, Arabic, Hebrew, Devanagari
and Bengali, and the East Asian scripts described below. Honorifics,
conjunctions and name particles written in them are recognized out of
the box, as far as each script's vocabulary reaches: each of those
scripts but katakana ships honorifics, while conjunctions and particles
reach fewer — Cyrillic and Greek ship conjunctions and no particle,
Hebrew particles and no conjunction, and Devanagari, Bengali, Han,
Hangul and hiragana honorifics only.

.. doctest::

    >>> from nameparser import parse
    >>> shaikh = parse("الشيخ محمد بن سلمان")
    >>> shaikh.title, shaikh.given, shaikh.family
    ('الشيخ', 'محمد', 'بن سلمان')
    >>> parse("عبد الرحمن محمد").given
    'عبد الرحمن'

Adding a word the defaults hold back
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Native-script entries are safe to enable by default precisely because
they cannot collide with Latin-script names. That rules out the
reverse: transliterations like ``sri``/``shri`` are *not* in the
default vocabulary, because they are also ordinary given names in
Latin script (``locales.HI`` turns ``shri`` on, for data where it is
the salutation). The same conservatism holds back a handful of native
entries that collide within their own script — bare ``سيد`` and
``شيخ`` (common given names) and Hebrew ``רב`` (an ordinary word).

If your data is homogeneous enough that a collision can't occur, the
reasoning behind the default doesn't apply to you — add the entry:

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> sayyid_lex = Lexicon.default().add(
    ...     "سيد", kind="title", addresses="given")
    >>> sayyid = Parser(lexicon=sayyid_lex).parse("سيد محمد")
    >>> sayyid.title, sayyid.given
    ('سيد', 'محمد')

One reading, a title, with the property ``addresses="given"``, which
says the honorific precedes the *given* name — as Arabic ones do — so
the word after it isn't read as a family name.

.. _east-asian-packs:

Which East Asian names need a pack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A name written in its own script with a space between its parts needs
no pack. Written wholly in Han or Hangul, or in Japanese kanji and kana
other than katakana alone, it is read family-first by default, because
the script alone settles the order (:ref:`east-asian-names`). A name only in katakana keeps
the default order, since it may be a transcribed foreign name.

A name written with no space has to be divided first, and the script
settles that only for Korean:

- **Korean** (``김민준``): no pack. An unspaced hangul name is split
  into surname and given name by default.
- **Chinese** (``毛泽东``): turn on ``zh``, with
  ``parser_for(locales.ZH)``. Without it the name stays one word, read
  as the family name.
- **Japanese** (``山田太郎``): turn on ``ja`` and pass a segmenter, with
  ``parser_for(locales.JA, segmenter=locales.ja_segmenter())``.

Neither pack is a default, because the same Han characters can be a
Chinese or a Japanese name, divided in different places: each is for
data whose language you can declare
(:ref:`splitting-unspaced-names`). The two defaults, the family-first
order and the Korean split, can each be turned off
(:ref:`east-asian-defaults`).

Using a pack
------------

Most packs carry one of two things: a *structural* rule, like reordering
a patronymic, that vocabulary alone can't express, or words that are
right in one language and wrong as a default (`Packs that choose a
language`_). Two packs, ``zh`` and ``ja``, also divide a name written
with no space, ``ja`` only with a segmenter (:ref:`east-asian-packs`).

:func:`~nameparser.parser_for` folds one or more packs onto a base
:class:`~nameparser.Parser` (the module default, unless you pass
``base=``). Here the Russian pack reads "Сидоров Иван Петрович"
(Sidorov Ivan Petrovich — surname/given/patronymic order) the way a
formal Russian document intends:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> ru = parser_for(locales.RU)
    >>> ru.parse("Сидоров Иван Петрович").given
    'Иван'

Enable a pack only for data that is predominantly in the shape or the
language it is for: for ``ru``, East Slavic names, since it reorders
any name of exactly three name words whose last has a patronymic
ending and whose middle one does not (`What a pack costs`_). If your input mixes traditions, parse the subsets separately
with different parsers rather than enabling a pack over all of it.
`Shipped packs`_ lists every pack and what it is for.

.. _what-a-pack-costs:

What a pack costs
~~~~~~~~~~~~~~~~~

Each pack declares a surface, the names it may read differently from
the default. A rule's surface is a shape — a patronymic ending or marker for ``ru`` and
``tr_az``, a script for ``zh`` and ``ja``, three name words or more for
the packs that read two family names — and a choice of languages
declares the words whose reading it changes.

Read that precisely: a shape is a pattern, not a language, so a pack
can act on a name from a tradition it was not written for. A broad
shape covers much:

- ``es``, ``es_ar``, ``cs``, ``sk``, ``pt_br`` and ``pt_pt`` may read
  any name of three words differently.
- ``vi``, whose name order is its shape, may read any name differently:
  the order moves every name a family comma does not fix, and its
  titles and removed readings reach the comma names too.
- ``mn`` may read any name written wholly in Cyrillic differently.
- ``ms`` may read any name holding ``Puan``, ``Cik``, ``Ustaz``,
  ``Ustazah``, ``Cikgu``, ``Tun``, ``Haji``, ``Dato``, ``Tan`` or ``Sri``
  as a word differently.
- ``my`` may read any name holding ``U`` or ``Daw`` as a word
  differently, with or without its full stop, or ``U`` as a letter of
  a word joined by full stops. Chosen strictly, it may read any name
  differently that holds another language's word (:ref:`strict-choice`).

.. warning::

   A pack declares a name *shape*, not a language (save one that
   chooses languages, such as ``ne``, which names a language yet acts
   on every name holding one of its words, whatever language that name
   is in). Either way, it cannot tell whose name it is looking at. Any surname that happens to end in a
   patronymic suffix matches the East Slavic rule, including names
   that are not East Slavic at all:

   .. doctest::

       >>> ru = parser_for(locales.RU)
       >>> abramovich = ru.parse("David Michael Abramovich")
       >>> abramovich.given, abramovich.family
       ('Michael', 'David')

   The default parser reads that as given ``David``, family
   ``Abramovich``. This is the trade the pack asks you to make, and it
   is why packs are opt-in rather than automatic.

Every shipped pack is held to the same test: over the test corpus and
the pack's own example names, every name it reads differently from the
default is one its declared surface covers. The contract is written
for the maintainers, who build the shipped packs, in
`nameparser/locales/AGENTS.md
<https://github.com/derek73/python-nameparser/blob/master/nameparser/locales/AGENTS.md>`__.

Finding packs by code
~~~~~~~~~~~~~~~~~~~~~

Find what's shipped with :func:`~nameparser.locales.available`, and
look one up dynamically by its lowercase code with
:func:`~nameparser.locales.get`:

.. doctest::

    >>> locales.available()
    ('ar', 'bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'he', 'hi', 'hr', 'ja', 'mn', 'ms', 'my', 'ne', 'nl', 'pt', 'pt_br', 'pt_pt', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')
    >>> locales.get("ru") is locales.RU
    True

The command line accepts the same codes: ``python -m nameparser
--locale ru --json "Сидоров Иван Петрович"`` applies the pack before
parsing, equivalent to ``parser_for(locales.get("ru"))``. ``--locale
ja`` also attaches :func:`~nameparser.locales.ja_segmenter` where
``nameparser[ja]`` is installed, which ``parser_for`` never does on its
own (:ref:`japanese-segmenter`). A code no pack has but a vocabulary file
does (``--locale ko``) chooses that language alone, and ``--strict``
makes the choice strict (`Reading one language only`_).

.. _shipped-packs:

Shipped packs
-------------

Each row says what a pack is for and what it turns on, and links to the
section that holds its detail and its costs. `What each pack carries`_
says which parts each pack is made of.

.. list-table::
   :header-rows: 1
   :widths: 9 19 44 28

   * - Code
     - For
     - Turns on
     - Example
   * - ``ar``
     - Arabic: Tunisian family names opening with ``Ben``
     - Chooses ``ar``, which reads ``Ben`` inside a name as the particle
       opening the family name. See :ref:`Maghrebi, Amazigh and Hebrew
       particles <maghrebi-hebrew-particles>`.
     - ``Karim Ben Haddad`` → family ``Ben Haddad``
   * - ``bn``
     - Bengali: romanized titles
     - Chooses ``bn``, which reads the romanized salutations ``Smt``
       and ``Shrimati`` (Mrs.) and the academic title ``Adhyapak``
       (professor) as titles, where the default reads a name word. See
       :ref:`Romanized Indic titles <romanized-indic-titles>`.
     - ``Smt Mamata Banerjee`` → title ``Smt``
   * - ``cs``, ``sk``
     - Czech and Slovak
     - Each chooses its one language, which turns on the generations
       ``ml.`` and ``st.`` and the titles and degrees the default leaves
       off, and reads two family names. See
       :ref:`west-south-slavic-packs`.
     - ``Alena Pešová Řehořová`` → family ``Pešová Řehořová``
   * - ``sl``, ``hr``
     - Slovenian and Croatian
     - Each chooses its one language, which turns on the generations
       ``ml.`` and ``st.``, and reads two family names. See
       :ref:`west-south-slavic-packs`.
     - | ``Ivan Horvat ml.`` → suffix ``ml.``
       | ``Ana Puž Kukuljan`` → family ``Puž Kukuljan``
   * - ``es``
     - Spanish
     - Chooses ``es``, which turns on the titles the default leaves off
       (``Maestra``, ``Doña``) and reads ``Lady`` as a given name, and
       reads two family names, guarded by a list of Spanish given names.
       See :ref:`Spanish and Portuguese titles
       <spanish-portuguese-titles>` and `A name another language's
       title spells: Hon, Lady`_.
     - | ``Maestra Ana Ruiz`` → title ``Maestra``
       | ``Gabriel García Márquez`` → family ``García Márquez``
   * - ``es_ar``
     - Argentine Spanish
     - ``es`` with a longer given-name list, for a second given name
       written before a single surname. See :ref:`Spanish and
       Portuguese titles <spanish-portuguese-titles>`.
     - ``Pablo Sebastián Rosales`` → family ``Rosales``, where ``es``
       gives ``Sebastián Rosales``
   * - ``ga``
     - Irish
     - Chooses ``ga``, which turns on the clan particles ``Nic``,
       ``Mhic``, ``Uí`` and ``Mic``. See :ref:`gaelic-clan-particles`.
     - ``Máire Uí Bhriain`` → family ``Uí Bhriain``
   * - ``gd``
     - Scottish Gaelic
     - Chooses ``gd``, which turns on the clan particle ``Nic``. See
       :ref:`gaelic-clan-particles`.
     - ``Màiri Nic Leòid`` → family ``Nic Leòid``
   * - ``he``
     - Hebrew: Israeli family names opening with ``Ben``, in Latin
       letters
     - Chooses ``he``, which reads ``Ben`` inside a name as the particle
       opening the family name. See :ref:`Maghrebi, Amazigh and Hebrew
       particles <maghrebi-hebrew-particles>`.
     - ``Yael Ben Arieh`` → family ``Ben Arieh``
   * - ``hi``
     - Hindi: romanized titles
     - Chooses ``hi``, which reads the romanized salutations ``Smt``
       and ``Shrimati`` (Mrs.) and ``Shri`` and ``Shriyut`` (Mr.) as titles, where
       the default reads a name word. See :ref:`Romanized Indic titles
       <romanized-indic-titles>`.
     - ``Shrimati Indira Gandhi`` → title ``Shrimati``
   * - ``ja``
     - Japanese names written with no space
     - Activates division of an unspaced Japanese name, which acts only
       with a segmenter passed beside it
       (:ref:`japanese-segmenter`), and chooses ``ja``, which turns on
       the honorific ``君`` (:ref:`Which honorifics peel when glued
       <glued-honorifics>`).
     - ``山田太郎`` → family ``山田``, given ``太郎``
   * - ``mn``
     - Mongolian names in Cyrillic
     - Reads a name written wholly in Cyrillic family first, the given
       name last, so the father's name, written first, is the family.
       See :ref:`Mongolian names <mongolian-names>`.
     - ``Батын Сүхээ`` → family ``Батын``, given ``Сүхээ``
   * - ``ms``
     - Malay: Malaysian titles
     - Chooses ``ms``, which reads the salutations ``Puan`` (Mrs.) and
       ``Cik`` (Miss), ``Ustaz``, ``Ustazah`` and ``Cikgu``, and the
       honours ``Tun``, ``Haji``, ``Dato``, ``Tan Sri`` and ``Puan Sri``,
       as titles, where the default reads a name word. See
       :ref:`malay-names`.
     - ``Puan Siti binti Ahmad`` → title ``Puan``
   * - ``my``
     - Burmese
     - Chooses ``my``, which reads the honorifics ``U`` and ``Daw``
       as titles (``U Thein Sein``). Choose it strictly for a list of
       nothing but Burmese names, which keeps ``San``, ``Van`` and the
       other syllables name words where other languages read particles
       or credentials. See :ref:`burmese-names`.
     - ``U Thein Sein`` → title ``U``, given ``Thein``, family ``Sein``
   * - ``ne``
     - Nepali
     - Chooses ``ne``, which reads ``श्री``, ``गुरु`` and ``Guru`` as
       name words where the default reads titles, each staying a title
       inside a title phrase (``His Holiness Guru Prasad``), and turns
       on ``initials_as_family``. See :ref:`nepali-given-names`.
     - | ``श्री कृष्ण श्रेष्ठ`` → given ``श्री``
       | ``Ram Bahadur B K`` → family ``B K``
   * - ``nl``
     - Dutch: family names opening with ``ten``
     - Chooses ``nl``, which reads ``ten`` inside a name as the particle
       opening the family name. See :ref:`dutch-particles`.
     - ``Jan ten Brink`` → family ``ten Brink``
   * - ``pt``
     - Portuguese, from any country
     - Chooses ``pt``, which settles Portuguese's clashes its way
       (``do`` a particle, not the DO credential). See
       :ref:`portuguese-packs`.
     - ``Maria da Piedade Costa`` → middle ``da Piedade``
   * - ``pt_br``
     - Brazilian Portuguese
     - Chooses ``pt-BR``, and with it ``pt``, turns on ``SB``, the
       agnomen Sobrinho as Brazilian filings abbreviate it, and reads
       two family names, guarded by a list of Portuguese given names.
       See :ref:`portuguese-packs` and :ref:`portuguese-two-family-names`.
     - | ``JOSE CARLOS SILVA SB`` → suffix ``SB``
       | ``Tiago Barros Queiroz`` → family ``Barros Queiroz``
   * - ``pt_pt``
     - Portuguese from Portugal
     - ``pt`` with two family names and ``pt_br``'s given-name list, and
       ``do Rosário``, ``do Carmo``, ``da Conceição`` and ``da Luz`` as given names. See
       :ref:`portuguese-two-family-names` and :ref:`portuguese-packs`.
     - ``Rui Sousa Pinto`` → family ``Sousa Pinto``, where ``pt`` gives
       ``Pinto``
   * - ``ru``
     - East Slavic names in formal order
     - Detects the family/given/patronymic shape by the patronymic's
       ending and assigns it accordingly. See
       :ref:`east-slavic-patronymics`.
     - ``Сидоров Иван Петрович`` → given ``Иван``
   * - ``tr_az``
     - Turkic names ending in a patronymic marker
     - Detects a name of three or four words ending in a marker word
       (``oglu``, ``qizi``, ``uulu``) and reads a four-word name's
       first word as the family name. See
       :ref:`turkic-patronymic-markers`.
     - ``Aliyev Ilham Heydar oglu`` → family ``Aliyev``
   * - ``vi``
     - Vietnamese
     - Reads every name family first, the given name last, keeps
       Vietnamese syllables such as ``Van``, ``Le`` and ``Do`` as name
       words, and chooses ``vi``, which turns on the academic titles
       ``TS``, ``GS`` and ``PGS``. See :ref:`Vietnamese names
       <vietnamese-names>`.
     - ``Nguyen Van Anh`` → family ``Nguyen``, middle ``Van``, given
       ``Anh``
   * - ``zh``
     - Chinese names written with no space
     - Splits an unspaced Han name into surname and given name against
       the surname list the pack ships. See
       :ref:`splitting-chinese-names`.
     - ``毛泽东`` → family ``毛``, given ``泽东``

.. _what-a-pack-carries:

What each pack carries
~~~~~~~~~~~~~~~~~~~~~~

A pack is made of up to three things, and which of them it carries
says what it can change:

- **A choice of languages** turns on readings the default vocabulary
  already holds for that language, written in its language's file
  (``ne.toml`` for Nepali) and off until a caller chooses it. Where
  the language reads a word its own way, the choice also turns off
  other languages' readings of that word (:ref:`choosing-languages`).
- **Policy fields** change how a name is read whatever its words are.
- **A word list** of the pack's own.

.. list-table::
   :header-rows: 1
   :widths: 30 14 28 28

   * - Pack
     - Chooses a language
     - Policy fields
     - Word list
   * - ``ar``, ``bn``, ``ga``, ``gd``, ``he``, ``hi``, ``hr``, ``ms``,
       ``nl``, ``pt``, ``sl``
     - yes
     - none
     - none
   * - ``cs``
     - yes
     - ``two_family_names``
     - a removal: ``Ing``'s given-name reading
   * - ``sk``
     - yes
     - ``two_family_names``
     - none
   * - ``es``, ``es_ar``, ``pt_br``, ``pt_pt``
     - yes
     - ``two_family_names``
     - the given names that switch leaves where they stand
   * - ``ja``
     - yes (turns on ``君``)
     - ``segment_scripts``, which needs a segmenter to act
     - none
   * - ``mn``
     - yes (turns on nothing)
     - a ``script_orders`` entry for Cyrillic
     - none
   * - ``my``
     - yes
     - none
     - none
   * - ``ne``
     - yes
     - ``initials_as_family``
     - none
   * - ``vi``
     - yes
     - ``name_order``
     - none; it takes readings out instead
   * - ``ru``, ``tr_az``
     - no
     - ``patronymic_rules``
     - none
   * - ``zh``
     - no
     - ``segment_scripts``, for the script its list covers
     - a surname list

``vi`` is the pack whose own fragment takes readings out rather than
adding them (`What a pack's lexicon may hold`_).

See :ref:`config-containers` for how that split (language vocabulary
vs. behavior) is drawn. Which half a new naming rule belongs in is
part of the contract for whoever builds a shipped pack, in
`nameparser/locales/AGENTS.md
<https://github.com/derek73/python-nameparser/blob/master/nameparser/locales/AGENTS.md>`__;
to propose a pack, `open an issue first
<https://github.com/derek73/python-nameparser/blob/master/CONTRIBUTING.md>`__.

.. _east-slavic-patronymics:

East Slavic patronymics (``ru``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Turn on ``ru`` when your data is East Slavic names in the order a
formal document writes them: family name, given name, patronymic. The
default, reading given-first, takes the family name for the given name
and the patronymic for the family.

The pack detects that shape and assigns it accordingly. The shape is
three name words, the last ending like a patronymic (Cyrillic and
transliterated ``-ovich``/``-ovna``-style endings, and the Ukrainian
``-івна``, ``-ївна``, ``-євич`` and ``Ілліч`` in Cyrillic), the middle
not, and no initial before the last, so ``И. Б. Зубкевич`` keeps family
``Зубкевич``:

.. doctest::

    >>> parse("Sidorova Anna Ivanovna").family
    'Ivanovna'
    >>> ivanovna = ru.parse("Sidorova Anna Ivanovna")
    >>> ivanovna.family, ivanovna.given
    ('Sidorova', 'Anna')
    >>> ru.parse("И. Б. Зубкевич").family
    'Зубкевич'

The pack also fills the ``patronymic`` view. A name written in the
spoken order, given name, patronymic, family name, is not reordered,
and its middle name with the ending fills ``patronymic`` too:

.. doctest::

    >>> ivanov = ru.parse("Ivan Ivanovich Ivanov")
    >>> ivanov.middle, ivanov.patronymic
    ('Ivanovich', 'Ivanovich')
    >>> ivanovna.patronymic
    'Ivanovna'

The rule reads the shape, not the language, so it reorders a name from
another tradition whose last word has the ending (`What a pack
costs`_).

.. _turkic-patronymic-markers:

Turkic patronymic markers (``tr_az``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Turn on ``tr_az`` when your data is Azerbaijani, Uzbek, Kyrgyz or other
Turkic names written with a patronymic marker: the father's name
followed by a standalone marker word (``oglu``, ``qizi``, ``uulu``, and
their Latin- and Cyrillic-script variants, ``o‘g‘li`` with any
apostrophe Uzbek text writes). The default reads the marker, the last
word, as the family name.

What the pack reads depends on how many words the name has:

- **A name of four words ending in a marker** has its first word read
  as the family name.
- **A name of three name words ending in one** has no surname, so the
  father's name and the marker are the family.

Either way the marker and the name before it fill ``patronymic``:

.. doctest::

    >>> parse("Aliyev Ilham Heydar oglu").family
    'oglu'
    >>> turkic = parser_for(locales.TR_AZ)
    >>> oglu = turkic.parse("Aliyev Ilham Heydar oglu")
    >>> oglu.family, oglu.given, oglu.patronymic
    ('Aliyev', 'Ilham', 'Heydar oglu')
    >>> uulu = turkic.parse("Bekmyrza Cholponbai uulu")
    >>> uulu.given, uulu.family, uulu.patronymic
    ('Bekmyrza', 'Cholponbai uulu', 'Cholponbai uulu')

.. _patronymic-packs-family-first:

Patronymic packs under a family-first order
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A declared family-first ``name_order`` stands down both patronymic
rotations (``ru`` and ``tr_az``) instead of competing with them:

- **Family first, then the given name** (``FAMILY_FIRST``): the two
  never disagree on a name the rule matches. That order already reads ``"Сидоров Иван Петрович"`` as
  family ``Сидоров``, so the pack's rotation adds nothing to a base
  built with it, and the pack still fills ``patronymic`` there
  (``Петрович``).
- **Family first, the given name last**
  (``FAMILY_FIRST_GIVEN_LAST``): the declared order wins, and the
  last word — the patronymic, or a separate ``oglu``/``qizi`` marker —
  reads as the given name.

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Parser, Policy
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> sidorov = family_first.parse("Сидоров Иван Петрович")
    >>> sidorov.family, sidorov.patronymic
    ('Сидоров', '')
    >>> declared = parser_for(locales.RU, base=family_first)
    >>> petrovich = declared.parse("Сидоров Иван Петрович")
    >>> petrovich.family, petrovich.patronymic
    ('Сидоров', 'Петрович')

``patronymic`` does not stand down, but under ``ru`` it reads only a
middle name with the ending, so it follows the order: under
``FAMILY_FIRST`` ``Ivan Ivanovich Ivanov`` reads given ``Ivanovich``
and no patronymic. Under ``tr_az`` a marker and the word before it are
read under every order.

A script order stands a rotation down too, as ``mn``'s does for a name
in Cyrillic (`A script order beside a patronymic pack`_).

.. _nepali-given-names:

Nepali given names (``ne``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Turn on ``ne`` when your data is Nepali names. The choice reads Hindi
and Marathi names too, where ``श्री`` is usually the salutation (Mr.),
so use it for Nepali data.

The pack chooses the language ``ne``, which reads ``श्री``, ``गुरु`` and
``Guru`` as name words, where the default reads them as titles. A name
opening with one of them reads it as a name word, placed by position as
any other is, a listed title in front of it included: the given name in
the default order (``श्री कृष्ण श्रेष्ठ`` → given ``श्री``, where the
default gives title ``श्री``), the family name under a family-first one.
Each stays a title inside a title phrase (``His Holiness Guru
Prasad``).

.. doctest::

    >>> ne = parser_for(locales.NE)
    >>> parse("Guru Prasad Sharma").title
    'Guru'
    >>> guru = ne.parse("Guru Prasad Sharma")
    >>> guru.title, guru.given, guru.family
    ('', 'Guru', 'Sharma')
    >>> ne.parse("Mr. Guru Sharma").given
    'Guru'
    >>> parser_for(locales.NE, base=family_first).parse("Guru Prasad Sharma").family
    'Guru'
    >>> ne.parse("His Holiness Guru Prasad").title
    'His Holiness Guru'

The pack also turns ``initials_as_family`` on, so a surname written as
its initials is the family (see :ref:`initials-as-family`):

.. doctest::

    >>> bahadur = parse("Ram Bahadur B K")
    >>> bahadur.middle, bahadur.family
    ('Bahadur B', 'K')
    >>> ne.parse("Ram Bahadur B K").family
    'B K'

.. _language-packs:

Packs that choose a language
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some words are right in one language and wrong as a default, because
another language written in the same script reads them differently. A
pack that chooses a language turns that language's reading of them on,
and each word is then read as its language reads the full word.
:ref:`choosing-languages` says how a choice works, and what it costs:
a choice settles every clash its language has a reading for, and that
costs the other languages' readings of those words.

Most of these packs are described in :doc:`languages`, where the table
above links each. Two groups are described here: the Irish and Scottish
Gaelic packs (:ref:`gaelic-clan-particles`), and the Portuguese ones,
which turn on ``da Piedade``, in ``pt_br`` ``SB``, in ``pt_pt``
``do Rosário``, ``do Carmo``, ``da Conceição`` and ``da Luz``, and in ``pt_br`` and
``pt_pt`` two family names (:ref:`portuguese-packs`).

.. _gaelic-clan-particles:

Irish and Scottish Gaelic clan particles (``ga``, ``gd``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Turn on ``ga`` for Irish names and ``gd`` for Scottish Gaelic ones.
Irish writes a woman's surname with ``Nic`` (daughter of) or, married,
``Uí`` (of the descendant of) before it, but ``Nic`` is also the short
form of Nicholas, so the default reads none of them. ``ga`` turns on
``Nic``, the married forms ``Mhic`` and ``Uí``, and ``Mic``; ``gd``
turns on ``Nic``:

.. doctest::

    >>> parse("Máire Uí Bhriain").family
    'Bhriain'
    >>> parser_for(locales.GA).parse("Máire Uí Bhriain").family
    'Uí Bhriain'
    >>> parser_for(locales.GD).parse("Màiri Nic Leòid").family
    'Nic Leòid'

``Nic`` and ``Mic`` are also given names, so in a name read given-first
one opening it stays the given name (``Nic Cage``), as ``Mac`` does by
default; under a family-first order it is the first word, read as the
family name. Either way it reports its doubt in ``ambiguities``.

The choice costs English's reading of ``MC``: under ``ga`` and
``gd``, ``Mc`` is the clan particle, so ``John Smith MC`` gives family
``MC`` and loses the Military Cross.

.. _portuguese-packs:

Portuguese (``pt``, ``pt_br``, ``pt_pt``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Turn on ``pt`` for Portuguese names from any country, ``pt_br`` for
Brazilian ones and ``pt_pt`` for names from Portugal: ``pt_br`` chooses
``pt-BR`` and ``pt_pt`` ``pt-PT``, each with ``pt``, so each does
everything ``pt`` does. ``pt_br`` and ``pt_pt`` also read two family
names, and ``pt`` does not; :ref:`portuguese-two-family-names` says
why, and how to turn the switch on beside ``pt``.

The three packs turn on a Portuguese given name written
behind a particle that is too rare to read by default (``da
Piedade``), so the phrase reads as a middle name, as ``das Graças``
does by default (see :ref:`two-given-names`):

.. doctest::

    >>> parse("Maria da Piedade Costa").family
    'da Piedade Costa'
    >>> piedade = parser_for(locales.PT).parse("Maria da Piedade Costa")
    >>> piedade.middle, piedade.family
    ('da Piedade', 'Costa')

``pt_pt`` also reads four such phrases that Portugal's names support
and Brazil's refute: ``do Rosário``, ``do Carmo``, ``da Conceição`` and ``da Luz``. ``pt`` and ``pt_br`` read them as the
start of the family:

.. doctest::

    >>> parser_for(locales.PT_BR).parse("Maria do Rosário Pinto").family
    'do Rosário Pinto'
    >>> rosario = parser_for(locales.PT_PT).parse("Maria do Rosário Pinto")
    >>> rosario.middle, rosario.family
    ('do Rosário', 'Pinto')

``do Rosario``, without the accent, every pack's plain choice reads as a
middle name, as Spanish ``del Rosario`` is read; a strict choice of
``pt`` or ``pt_br``, which leaves Spanish out, reads it as the family.

``pt_br`` also turns on ``SB``. Brazilian filings abbreviate the
agnomen *Sobrinho* (nephew) to ``SB``, which is also the S.B. degree,
so the default does not read it. Under the pack it is a suffix only
where the name keeps a family name without it (``Ana SB`` keeps family
``SB``), and it reports its doubt in ``ambiguities``:

.. doctest::

    >>> parse("JOSE CARLOS SILVA SB").family
    'SB'
    >>> sobrinho = parser_for(locales.PT_BR).parse("JOSE CARLOS SILVA SB")
    >>> sobrinho.family, sobrinho.suffix
    ('SILVA', 'SB')

The choices cost the other languages' readings of the words they
settle:

- **Under pt, pt_br and pt_pt,** the words read as ``pt`` reads them: ``do`` is
  the particle, not the DO credential, so ``John Smith DO`` gives
  family ``DO`` under ``pt`` (``Smith DO`` under ``pt_br`` and
  ``pt_pt``, which read two family names). ``Sr`` keeps both readings, *Senhor* in front and
  "Senior" behind, as in the default, under ``es`` too.
- **Under pt_br,** a written S.B. degree reads as Sobrinho
  (``Howard Gordon, MD SB`` fills ``generation`` with ``SB``).

Stacking packs
--------------

Pass more than one pack and they fold together in order:

.. doctest::

    >>> both = parser_for(locales.RU, locales.TR_AZ)
    >>> sorted(rule.name for rule in both.policy.patronymic_rules)
    ['EAST_SLAVIC', 'TURKIC']

How each part combines:

- **Languages union** into one choice, with the base's own, applied
  first (see `Choosing languages`_), so the order the packs are given
  in does not change it.
- **Lexicons join in order**: the packs' lexicons in the order given,
  then the base's, each applied after the choice, so where two
  disagree the later wins and the base's own words win over every
  pack's (`Your own words outrank a choice`_).
- **Set-valued policy fields union** the same way — the fields
  declared set-valued in :class:`~nameparser.PolicyPatch`:
  ``patronymic_rules``, ``segment_scripts`` and the delimiter fields.
- **Script orders merge by script** (``script_orders``): a pack's entry replaces the
  base's entry for its script and the other entries stand, so ``mn``
  adds its Cyrillic order to your table, opt-outs included; two packs
  setting one script to different orders warn, and the later wins.
- **Every other, scalar field is later-wins.** If two packs with
  different codes set the same scalar field to different values, the
  later one wins and a ``UserWarning`` is raised; two that set it to the
  same value agree, so ``parser_for(locales.CS, locales.SK)``, which
  both turn ``two_family_names`` on, is silent. A pack overrides the base
  parser's value silently.

A script order beside a patronymic pack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A script order takes a name before a patronymic rule does: the East
Slavic and Turkic rotations stand down where an order is declared, so
beside ``mn`` the ``ru`` and ``tr_az`` rules no longer reorder a name
written wholly in Cyrillic, which ``mn`` reads father's name first:

.. doctest::

    >>> parser_for(locales.RU).parse("Сидоров Иван Петрович").family
    'Сидоров'
    >>> parser_for(locales.RU).parse("Сидоров Иван Петрович").given
    'Иван'
    >>> parser_for(locales.MN, locales.RU).parse("Сидоров Иван Петрович").given
    'Петрович'

.. _choosing-languages:

Choosing languages
------------------

Choose a language when you know which language your names are in and
the default reads one of their words another language's way. The
default vocabulary is written one word at a time, each in the file
of the language whose names it occurs in, and the default reads every
language's words at once. Where two languages read one word
differently, the default keeps both readings and lets the name around
the word decide: Portuguese ``e`` ("and") is also an initial, so in a
name written wholly in capitals it reads as the initial and reports the
doubt.

What a choice changes
~~~~~~~~~~~~~~~~~~~~~

A :class:`~nameparser.Locale` with ``languages`` chooses languages,
written as BCP 47 tags. A chosen language's readings win on a word it
has a vocabulary reading of, and a reading its file holds off by
default is turned on. Under Portuguese, ``E`` is the connective:

.. doctest::

    >>> from nameparser import Lexicon, Locale, parse, parser_for
    >>> parse("ANA SILVA E SOUZA").family
    'SOUZA'
    >>> pt = Locale(code="pt", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"pt"}))
    >>> parser_for(pt).parse("ANA SILVA E SOUZA").family
    'SILVA E SOUZA'

The shipped packs that choose no language (``ru``, ``tr_az``, ``zh``)
turn no shipped reading on or off: they leave the base parser's
vocabulary as it was, save for ``zh``'s surname list. A pack's own
lexicon can still add or remove readings (`What a pack's lexicon may
hold`_).

What a choice costs
~~~~~~~~~~~~~~~~~~~

A choice costs the other languages' readings of the words it settles.
English holds ``DO`` as a credential (Doctor of Osteopathy) and
Portuguese ``do`` as a particle ("of the"), so each language, chosen
alone, reads the other's names by its own word:

.. doctest::

    >>> en = Locale(code="en", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"en"}))
    >>> parse("Maria do Carmo").family
    'do Carmo'
    >>> parser_for(en).parse("Maria do Carmo").family
    'Carmo'
    >>> parser_for(pt).parse("John Smith DO").family
    'DO'
    >>> parser_for(pt, en).parse("Maria do Carmo").family
    'do Carmo'

Choosing both keeps both readings, as the default does.

A reading that a word is borne as a name never settles anything: it
keeps the name around the word in charge, under any plain choice. A
strict choice keeps only the readings its chosen files hold, beside the
shared words and those in other scripts, so it drops a name reading
written in Latin letters in another language's file, as it drops any
other (`Reading one language only`_).

A name another language's title spells: Hon, Lady
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A name reading held off by default is how a language claims a word
another language's titles use. ``Lady`` is a given name across Latin
America and a British title. The default reads the title, and ``es``,
which :data:`~nameparser.locales.ES` chooses, reads the given name, the
title staying one in a phrase (``Hon Lady``, ``Lady Justice``, ``Lady
Chief Justice``, ``Lady Mayor``, ``Lady of``):

.. doctest::

    >>> parse("Lady Heidenreich").title
    'Lady'
    >>> parser_for(locales.ES).parse("Lady Heidenreich").given
    'Lady'
    >>> parser_for(locales.ES).parse("Lady Justice Jane Smith").title
    'Lady Justice'

The choice costs the title written bare. A peeress written with it
reads the given name under the choice, and the pack's two family names
then take her own given name into the family (``Lady Annabel
Goldsmith`` → given ``Lady``, family ``Annabel Goldsmith``).

``Hon`` is the same kind of word in Chinese: the British style (the
Honourable) and a Cantonese given name, so the default reads it as the
title and a Chinese choice (``zh``, or ``zh-HK``) as the given name,
the style staying a title inside a phrase (``The Hon``, ``Rt Hon``,
``Hon Mrs``) and written with its period:

.. doctest::

    >>> chinese = Locale(code="zh", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"zh"}))
    >>> parse("Hon Wah Yeung").title
    'Hon'
    >>> parser_for(chinese).parse("Hon Wah Yeung").given
    'Hon'
    >>> parser_for(chinese).parse("The Hon John Smith").title
    'The Hon'

That choice costs the style written bare at the head, as UK registers
and Hong Kong's legislature write it: ``Hon David Layton`` reads given
``Hon`` under it, and ``John Smith, Hon`` given ``Hon``, family ``John
Smith``.

The ``zh`` pack makes no choice of languages, so it leaves ``Hon`` a
title; the reading needs a :class:`~nameparser.Locale` with
``languages``.

A language with no pack
~~~~~~~~~~~~~~~~~~~~~~~

A language can have a file and no pack. Breton writes its article
``ar`` before the surname (``Katell ar Gall``), and the letters are
paired initials or the Arabic article in every other language's names,
so only a choice of ``br`` reads the particle:

.. doctest::

    >>> breton = Locale(code="br", lexicon=Lexicon.empty(),
    ...                 languages=frozenset({"br"}))
    >>> parse("Katell ar Gall").family
    'Gall'
    >>> parser_for(breton).parse("Katell ar Gall").family
    'ar Gall'

Which tags are accepted
~~~~~~~~~~~~~~~~~~~~~~~

A tag selects its own file and those of the languages it belongs to,
never the other way: ``pt-BR`` reads ``pt.toml`` too, and ``pt``
leaves the Brazilian words alone. No other table of related languages
is read, so a caller with Malay and Indonesian names chooses ``ms``
and ``id``.

Tags are compared without regard to case, and a tag is checked in one
of four ways:

- **A malformed tag** (``pt_BR``, ``p``) raises ``ValueError`` when the
  :class:`~nameparser.Locale` is built.
- **A tag no vocabulary file holds**, itself or any language it belongs
  to (``xx``), raises ``ValueError`` at
  :func:`~nameparser.parser_for`, naming the tags that have a file.
- **A region or other subtag of a language that has a file** (``pt-AO``)
  is accepted and reads that language's file, there being none of its
  own.
- **A language whose file holds no reading a parse reads yet**
  (``hu``, whose file records only words kept out and familiar forms, which only name matching reads) raises ``ValueError``, a plain choice
  of it changing nothing; a strict choice accepts it (`Which choices
  can be strict`_).

Chaining choices
~~~~~~~~~~~~~~~~

A parser records the languages it was chosen under, as
:attr:`Parser.languages <nameparser.Parser.languages>` (read from its
:attr:`Lexicon.languages <nameparser.Lexicon.languages>`), so a choice
made on top of a base built by an earlier call joins the base's: the
two read as one call choosing both.

.. doctest::

    >>> chained = parser_for(en, base=parser_for(pt))
    >>> sorted(chained.languages)
    ['en', 'pt']
    >>> chained.parse("Maria do Carmo").family, chained.parse("John Smith DO").suffix
    ('do Carmo', 'DO')
    >>> chained.lexicon == parser_for(pt, en).lexicon
    True

A chained call keeps its base's strictness (`Reading one language
only`_) unless it passes ``strict``: ``strict=True`` makes a plain
base's choice strict, with the call's languages joined to it, and
``strict=False`` on a strict base raises ``ValueError``, a strict choice
not being undone by a later call.

Your own words outrank a choice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A choice selects among the shipped readings; what you added or removed
with :meth:`Lexicon.add <nameparser.Lexicon.add>` and
:meth:`Lexicon.remove <nameparser.Lexicon.remove>` applies after it,
whichever was written first. Under ``en``, which reads ``do`` as a
credential, a base listing ``do`` and ``van`` as particles keeps both:

.. doctest::

    >>> from nameparser import Parser
    >>> mine = Lexicon(surnames=Lexicon.default().surnames).add(
    ...     "do", "van", kind="preposition")
    >>> chosen = parser_for(en, base=Parser(lexicon=mine)).lexicon
    >>> [w for w in ("do", "van")
    ...  if any(r.category == "particle" for r in chosen.readings_of(w))]
    ['do', 'van']

A pack's own lexicon is joined before yours, so where the two disagree
yours wins, and of two packs the later one wins.

A word of yours that
cannot stand beside a reading the choice turns on raises
``ValueError`` at :func:`~nameparser.parser_for`, naming your call and
the ``remove`` that resolves it: the Czech pack reads ``st.`` as a
generation (the elder), and a word holds one kind of suffix, so a
lexicon that added it as a credential is refused under ``locales.CS``.

A lexicon built from :meth:`Lexicon.empty
<nameparser.Lexicon.empty>` holds no shipped reading, so a choice turns
none on in it, strict or not: to read only the chosen languages'
vocabulary and the shared words, choose strictly over the default
lexicon.

.. _strict-choice:

Reading one language only
~~~~~~~~~~~~~~~~~~~~~~~~~

Make a choice strict, with ``parser_for(..., strict=True)``, for data
you know to be of one origin. A plain
choice still reads every other language's words: it settles only the
words its own language has a reading of. Names of a single origin
written in Latin letters meet those words by accident. Many common
Korean syllables, romanized, are spelled like another language's
word: ``Do`` like the Portuguese particle, ``Bin`` like the Arabic
and Malay one, ``Ae`` like an English credential. Korean's file holds
one word written in Latin letters, ``Ra``, which it reads as a family
name and a given name by default, so a ``ko`` choice settles none
of the others, and a strict one reads each as a name word:

.. doctest::

    >>> ko = Locale(code="ko", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"ko"}))
    >>> korean = parser_for(ko, strict=True)
    >>> parse("Kim Do Hyun").family
    'Do Hyun'
    >>> korean.parse("Kim Do Hyun").middle, korean.parse("Kim Do Hyun").family
    ('Do', 'Hyun')
    >>> parse("Kim Min Ae").suffix
    'Ae'
    >>> korean.parse("Kim Min Ae").family
    'Ae'

Chinese ``De`` is the same case under strict ``zh``: ``De Xu`` reads
given ``De``, family ``Xu``.

What a strict choice keeps
^^^^^^^^^^^^^^^^^^^^^^^^^^

A strict choice reads three things. A word none of them holds is read
as a name word, unless you listed it yourself (below) or its shape
alone gives it a role, as a shape gives an unlisted word one by
default: ``Mx.`` opening a name, with its period, is a title.

- **The chosen languages' files**, each tag selecting its own and its
  ancestors' (`Which tags are accepted`_).
- **The shared mul file**, the words every language writes alike,
  among them ``Dr``, ``Prof``, ``Mr``, ``Mrs``, ``Ms`` (the
  salutation and the degree), ``Miss``, ``Mister``, ``Madam``, the
  degrees ``PhD``, ``MSc``, ``MBA``, ``MPH`` and ``BSc``, the numerals
  and ``Jr``.
- **Words written in a script other than Latin** (the Korean, Japanese
  and Chinese honorifics, the Cyrillic and Devanagari titles), each
  selecting itself by its script and read as a plain choice of the
  same languages reads it.

Every other file's readings leave, even of a word ``mul`` also
holds (Catalan's and Polish's conjunction ``i`` beside the numeral).

What you configured yourself stays too:

- **Your own words stay.** A word a strict choice drops is kept where
  you added it yourself, your lexicon's readings applying after the
  choice (`Your own words outrank a choice`_).
- **A pack's own word list and policy stay.** They are applied after
  the strict choice, untouched, and so is the Korean surname list.

What a strict choice drops
^^^^^^^^^^^^^^^^^^^^^^^^^^

What a strict choice drops it drops from every name:

- **Other languages' words go with the accidents.** The shared words
  stay (``Kim Min Jun, PhD, MSc`` keeps both credentials), but the rest
  of the English credentials (``Kim Min Jun, RN`` reads given ``RN``;
  ``MD``, shared with ``Md`` for Muhammad, is kept), a bare ``Mx``, and an immigrant's particle from another language are
  read as name words. Where English context is part
  of the data, choose ``en`` too, which brings back its words and its
  costs alike:

  .. doctest::

      >>> korean.parse("Kim Min Jun, PhD, MSc").suffix
      'PhD, MSc'
      >>> parser_for(ko, en, strict=True).parse("Kim Min Ae").suffix
      'Ae'
      >>> korean.parse("Kim Min Jun, RN").given
      'RN'
      >>> parser_for(ko, en, strict=True).parse("Kim Min Jun, RN").suffix
      'RN'

- **The shared words are a default like any other.** Take one out of
  the lexicon you build on and no choice brings it back. (The example
  writes it ``Phd``: written ``PhD``, an unlisted word is still read as
  a credential by its capitals, see :ref:`all-caps-credentials`.)

  .. doctest::

      >>> no_phd = Parser(lexicon=Lexicon.default().remove(
      ...     "phd", kind="credential"))
      >>> korean.parse("Kim Min Jun, Phd").suffix
      'Phd'
      >>> parser_for(ko, base=no_phd, strict=True).parse(
      ...     "Kim Min Jun, Phd").given
      'Phd'

Which choices can be strict
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Strict needs a language.** A strict call whose packs choose none
  (``parser_for(locales.ZH, strict=True)``) would keep only the shared
  words and those in other scripts, so it raises ``ValueError`` and names a pack to
  add.
- **A language whose file holds no reading a parse reads yet is
  accepted.** ``hu.toml`` holds none, so a plain ``hu`` choice is
  refused (`Which tags are accepted`_); a strict one reads the other
  scripts' words and, in Latin
  letters, only the shared ones. Of the familiar forms and listed
  spellings, which only name matching reads, it keeps ``hu.toml``'s and
  the shared ones (``mul.toml``).

Creating your own Locale
-------------------------

You don't need to touch nameparser's registry to use your own pack —
:class:`~nameparser.Locale` is a plain, constructible value:
``Locale(code=..., lexicon=..., policy=PolicyPatch(...))``. A
:class:`~nameparser.PolicyPatch` is a :class:`~nameparser.Policy`-shaped
patch: every field defaults to :data:`~nameparser.UNSET` (leave it
alone) instead of to a concrete value, so a pack only ever states what
it changes. A patch can also be applied directly, without a pack —
see :meth:`Policy.patched() <nameparser.Policy.patched>`.

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, parser_for
    >>> kapitan_lex = Lexicon.empty().add("kapitan", kind="military")
    >>> corp_pack = Locale(code="mycorp", lexicon=kapitan_lex,
    ...                     policy=PolicyPatch(middle_as_family=True))
    >>> kapitan = parser_for(corp_pack).parse("Kapitan Anna Maria Schmidt")
    >>> kapitan.title, kapitan.given, kapitan.family
    ('Kapitan', 'Anna', 'Maria Schmidt')

That pack does two things at once: the :class:`~nameparser.Lexicon`
fragment teaches the parser that ``kapitan`` is a title, and the
:class:`~nameparser.PolicyPatch` turns on ``middle_as_family`` so any
remaining given-position words after the first fold into ``family``
instead of ``middle`` — compare this to the default parser's reading
of the same string, which has no title and splits ``given='Kapitan'``,
``middle='Anna Maria'``, ``family='Schmidt'``.

What a pack's lexicon may hold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``policy`` half is a patch, but the ``lexicon`` half is not. A
pack's :class:`~nameparser.Lexicon` is a complete value in its own
right, validated on its own, and it may hold any of these:

- **Readings, which are checked twice.** They are checked as they are
  added (a phrase, a ``may_be_initial`` on anything but a single cased
  letter, an agnomen with no name reading), and again when ``|`` joins
  them onto the base, where a reading that clashes with one the base
  holds raises with the pack's code. A fragment holding
  ``Lexicon.empty().add("dc", kind="generation")`` fails there, ``dc``
  being a credential in the default and a word holding one suffix
  kind.
- **A reading that marks another**, as a ``given`` reading makes a
  particle possibly given. It needs nothing else in the fragment:
  ``Lexicon.empty().add("mc", kind="given")`` marks the base's particle
  ``mc``.
- **A list and no reading.** ``zh`` is the shipped worked example: its
  ``Lexicon(surnames=...)`` holds a list and no reading.
- **Removals.** A fragment's ``remove`` calls apply after the choice
  too, as a caller's own do: ``vi``'s fragment,
  ``Lexicon.empty().remove("van", ..., kind="particle")`` with a call
  each for ``kind="conjunction"`` and ``kind="credential"``, takes out
  those readings of the syllables it lists, and only those (``mac``
  stays a particle, ``ma`` and ``md`` credentials). ``vi`` removes
  where another pack would choose because a choice prefers its
  language's reading of a word only where that reading is a title, a
  particle or another vocabulary kind, never a name, so no reading
  ``vi.toml`` could write would keep ``Van`` a name word. A strict
  choice settles the same clashes without a list, by reading no other
  language's words, which is how a wholly Burmese list is read
  (:ref:`burmese-names`).
