Locale packs
============

A locale pack is an opt-in bundle of policy, vocabulary and a choice
of languages, each where a naming tradition needs it, for one specific
pattern: East Slavic patronymics, Turkic patronymic markers, the
titles and particles of one language, and so on. Packs apply only
when you ask for one by name, and every pack is held to the same
test: over the test corpus and the pack's own example names, every
name it reads differently from the default is one its declared surface
covers. A rule's surface is a shape — a patronymic ending or marker
for ``ru`` and ``tr_az``, a script for ``zh`` and ``ja``, three name
words or more for the packs that read two family names — and a choice
of languages declares the words whose reading it changes. Read that precisely — a shape is a pattern, not a
language, so a pack can act on a name from a tradition it was not
written for, and a broad shape covers much: ``es``, ``es_ar``, ``cs``
and ``sk`` may read any name of three words differently, ``vi``, whose
name order is its shape, any name: the order moves every name a family
comma does not fix, and its titles and removed readings reach the comma
names too; and ``mn`` any name written wholly in Cyrillic. The warning
under `Using a pack`_ shows what that costs.

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
Latin script. The same conservatism holds back a handful of native
entries that collide within their own script — bare ``سيد`` and
``شيخ`` (common given names), Hebrew ``רב`` (an ordinary word), the
Arabic ``د.`` abbreviation (it would swallow initials).

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

East Asian names need no pack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A name written wholly in Han or Hangul, or in Japanese kanji and kana
other than katakana alone, is read family-first, and an unspaced hangul
name is split into surname and given name, by default, because the
script alone settles both (:ref:`east-asian-names`;
:ref:`east-asian-defaults` turns them off). A name only in katakana
keeps the default order, since it may be a transcribed foreign name.
Splitting an unspaced Han name is the exception: the same characters
can be a Chinese or a Japanese name, divided in different places, so
the ``zh`` and ``ja`` packs below turn it on for data whose language
you can declare.

A pack is for something different: a *structural* rule, like reordering
a patronymic, that vocabulary alone can't express, or words that are
right in one language and wrong as a default (`Packs that choose a
language`_).

Using a pack
------------

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

Stacking packs
~~~~~~~~~~~~~~

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
- **``script_orders`` merges by script**: a pack's entry replaces the
  base's entry for its script and the other entries stand, so ``mn``
  adds its Cyrillic order to your table, opt-outs included; two packs
  setting one script to different orders warn, and the later wins.
  A script order takes a name before a patronymic rule does: the East
  Slavic and Turkic rotations stand down where an order is declared, so
  beside ``mn`` the ``ru`` and ``tr_az`` rules no longer read a name
  written wholly in Cyrillic, which ``mn`` reads father's name first:

  .. doctest::

      >>> parser_for(locales.RU).parse("Сидоров Иван Петрович").family
      'Сидоров'
      >>> parser_for(locales.RU).parse("Сидоров Иван Петрович").given
      'Иван'
      >>> parser_for(locales.MN, locales.RU).parse("Сидоров Иван Петрович").given
      'Петрович'
- **Every other, scalar field is later-wins.** If two packs with
  different codes set the same scalar field to different values, the
  later one wins and a ``UserWarning`` is raised; two that set it to the
  same value agree, so ``parser_for(locales.CS, locales.SK)``, which
  both turn ``two_family_names`` on, is silent. A pack overrides the base
  parser's value silently.

.. _choosing-languages:

Choosing languages
~~~~~~~~~~~~~~~~~~

The default vocabulary is written one word at a time, each in the file
of the language whose names it occurs in, and the default reads every
language's words at once. Where two languages read one word
differently, the default keeps both readings and lets the name around
the word decide: Portuguese ``e`` ("and") is also an initial, so in a
name written wholly in capitals it reads as the initial and reports the
doubt.

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

Choosing both keeps both readings, as the default does. A reading
that a word is borne as a name never settles anything: it keeps the
name around the word in charge, under any plain choice. A strict
choice keeps only the readings its chosen files hold, beside the
shared words and those in other scripts, so it drops a name reading
written in Latin letters in another language's file, as it drops any
other
(`Reading one language only`_).

A name reading held off by default is how a language claims a word
another language's titles use. ``Hon`` is the British style (the
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

The choice costs the style written bare at the head, as UK registers
and Hong Kong's legislature write it: ``Hon David Layton`` reads given
``Hon`` under it, and ``John Smith, Hon`` given ``Hon``, family ``John
Smith``. The ``zh`` pack makes no choice of languages, so it leaves
``Hon`` a title; the reading needs a :class:`~nameparser.Locale` with
``languages``.

``Lady`` is the same kind of word in Spanish: a given name across Latin
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

A peeress written with the bare title reads the given name under it,
and the pack's two family names then take her own given name into the
family (``Lady Annabel Goldsmith`` → given ``Lady``, family ``Annabel
Goldsmith``).

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

A tag selects its own file and those of the languages it belongs to,
never the other way: ``pt-BR`` reads ``pt.toml`` too, and ``pt``
leaves the Brazilian words alone. No other table of related languages
is read, so a caller with Malay and Indonesian names chooses ``ms``
and ``id``. Tags are compared without regard to case, and a tag is
checked in one of four ways:

- **A malformed tag** (``pt_BR``, ``p``) raises ``ValueError`` when the
  :class:`~nameparser.Locale` is built.
- **A tag no vocabulary file holds**, itself or any language it belongs
  to (``xx``), raises ``ValueError`` at
  :func:`~nameparser.parser_for`, naming the tags that have a file.
- **A region or other subtag of a language that has a file** (``pt-PT``)
  is accepted and reads that language's file, there being none of its
  own.
- **A language whose file holds no reading a parse reads yet**
  (``hu``, whose file records only words kept out) raises ``ValueError``, a plain choice
  of it changing nothing; a strict choice accepts it (`Reading one language
  only`_).

A pack that chooses no language leaves the base parser's vocabulary
exactly as it was.

Chaining choices
^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
yours wins, and of two packs the later one wins. A word of yours that
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
^^^^^^^^^^^^^^^^^^^^^^^^^

A choice still reads every other language's words: it settles only the
words its own language has a reading of. Names of a single origin
written in Latin letters meet those words by accident. Many common
Korean syllables, romanized, are spelled like another language's
word: ``Do`` like the Portuguese particle, ``Bin`` like the Arabic
and Malay one, ``Ra`` like an English credential and a German academic
title. Korean's file holds no word written in Latin letters, so a
``ko`` choice settles none of them.

``parser_for(..., strict=True)`` makes the choice strict: only the
chosen languages' files are read, each tag selecting its own and its
ancestors' as above, plus every reading of a word written in a script
other than Latin (the Korean, Japanese and Chinese honorifics, the
Cyrillic and Devanagari titles), which selects itself by its script,
and the readings of the shared ``mul`` file, which every language
writes alike, among them ``Dr``, ``Prof``, ``Mr``, ``Mrs``, ``Ms`` (the
salutation and the degree), ``Miss``, ``Mister``, ``Madam``, the degrees
``PhD``, ``MSc``, ``MBA``, ``MPH`` and ``BSc``, the numerals and
``Jr``. Every other file's readings leave, even of a word ``mul`` also
holds (Catalan's and Polish's conjunction ``i`` beside the numeral), and
a word none of these holds is read as a name word:

.. doctest::

    >>> ko = Locale(code="ko", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"ko"}))
    >>> korean = parser_for(ko, strict=True)
    >>> parse("Kim Do Hyun").family
    'Do Hyun'
    >>> korean.parse("Kim Do Hyun").middle, korean.parse("Kim Do Hyun").family
    ('Do', 'Hyun')
    >>> parse("Kim Min Ra").suffix
    'Ra'
    >>> korean.parse("Kim Min Ra").family
    'Ra'

Chinese ``De`` is the same case under strict ``zh``: ``De Xu`` reads
given ``De``, family ``Xu``.

Strict is for data you know to be of one origin, and what it drops it
drops from every name:

- **Other languages' words go with the accidents.** The shared words
  stay (``Kim Min Jun, PhD, MSc`` keeps both credentials), but the rest
  of the English credentials (``Kim Min Jun, MD`` reads given ``MD``,
  ``MD`` staying English's since a leading ``Md`` abbreviates Muhammad),
  a bare ``Mx``, and an immigrant's particle from another language are
  read as name words. A shape still reads as it does by default:
  ``Mx.``, with its period, is a title. Where English context is part
  of the data, choose ``en`` too, which brings back its words and its
  costs alike:

  .. doctest::

      >>> korean.parse("Kim Min Jun, PhD, MSc").suffix
      'PhD, MSc'
      >>> parser_for(ko, en, strict=True).parse("Kim Min Ra").suffix
      'Ra'
      >>> parser_for(ko, en, strict=True).parse("Kim Min Jun, MD").suffix
      'MD'

- **The shared words are a default like any other.** Take one out of
  the lexicon you build on and no choice brings it back:

  .. doctest::

      >>> no_phd = Parser(lexicon=Lexicon.default().remove(
      ...     "phd", kind="credential"))
      >>> parser_for(ko, base=no_phd, strict=True).parse(
      ...     "Kim Min Jun, PhD").given
      'PhD'

- **Strict needs a language.** A strict call whose packs choose none
  (``parser_for(locales.ZH, strict=True)``) would keep only the shared
  words and those in other scripts, so it raises ``ValueError`` and names a pack to
  add. A pack's own word list and policy are applied after the strict
  choice, untouched, and so is the Korean surname list.
- **A language whose file holds no reading a parse reads yet is
  accepted.** ``hu.toml`` holds none, so a plain ``hu`` choice is
  refused; a strict one reads the other scripts' words and, in Latin
  letters, only the shared ones. It keeps no familiar form, which name
  matching reads: those are English alone, so a strict choice keeps
  them only where it chooses ``en``.
- **Your own words stay.** A word a strict choice drops is kept where
  you added it yourself, your lexicon's readings applying after the
  choice (`Your own words outrank a choice`_).

Finding packs by code
~~~~~~~~~~~~~~~~~~~~~

Find what's shipped with :func:`~nameparser.locales.available`, and
look one up dynamically by its lowercase code with
:func:`~nameparser.locales.get`:

.. doctest::

    >>> locales.available()
    ('bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'hi', 'hr', 'ja', 'mn', 'ne', 'pt', 'pt_br', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')
    >>> locales.get("ru") is locales.RU
    True

The command line accepts the same codes: ``python -m nameparser
--locale ru --json "Сидоров Иван Петрович"`` applies the pack before
parsing, equivalent to ``parser_for(locales.get("ru"))``. ``--locale
ja`` also attaches :func:`~nameparser.locales.ja_segmenter` where
``nameparser[ja]`` is installed, which ``parser_for`` never does on its
own (the ``ja`` row below). A code no pack has but a vocabulary file
does (``--locale ko``) chooses that language alone, and ``--strict``
makes the choice strict (`Reading one language only`_).

Shipped packs
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Code
     - Turns on
   * - ``bn``
     - Bengali — chooses ``bn``, which turns on the romanized
       salutations ``Smt`` and ``Shrimati`` (Mrs.) and the academic
       title ``Adhyapak`` (professor), read as titles where the default
       reads a name word (``Smt Mamata Banerjee`` → title ``Smt``). See
       :ref:`Romanized Indic titles <romanized-indic-titles>`.
   * - ``cs``, ``sk``
     - Czech and Slovak — a choice of that one language, which turns on
       the generations ``ml.`` and ``st.``, the academic titles the
       default leaves off (``MgA.``, ``BcA.``; for Czech also the rank
       ``mjr.``) and the degrees written
       after the name, and reads two
       family names (``Alena Pešová Řehořová`` → family ``Pešová
       Řehořová``, ``surname2`` ``Řehořová``), so two given names read as a given name and a family
       name (see :ref:`west-south-slavic-packs`).
   * - ``sl``, ``hr``
     - Slovenian and Croatian vocabulary — a choice of that one
       language, which turns on the generations ``ml.`` and ``st.``
       (see :ref:`west-south-slavic-packs`).
   * - ``es``
     - Spanish — chooses ``es``, which turns on the titles that lead a
       Spanish name and that the default leaves off for the names they
       spell (``Maestra``, ``Doña``; ``Maestra Ana Ruiz`` → title
       ``Maestra``), reads
       ``Lady`` as a given name (``Lady Heidenreich`` → given ``Lady``), and
       reads two family names, a list of Spanish given names keeping a
       given name out of the family (``Gabriel García Márquez`` →
       family ``García Márquez``, ``surname2`` ``Márquez``;
       ``José Luis Pérez`` → family
       ``Pérez``). See :ref:`Spanish and Portuguese titles <spanish-portuguese-titles>`.
   * - ``es_ar``
     - Argentine Spanish — ``es`` with a longer given-name list, one
       holding given names that Spain bears often enough as surnames
       to leave off ``es``'s list, which Argentine names write before a
       single surname (``Pablo Sebastián
       Rosales`` → family ``Rosales``, where ``es`` gives ``Sebastián
       Rosales``). See :ref:`Spanish and Portuguese titles <spanish-portuguese-titles>`.
   * - ``ga``
     - Irish — chooses ``ga``, which turns on the clan particles the
       default leaves off: ``Nic`` (daughter of), the married forms
       ``Mhic`` and ``Uí``, and ``Mic`` (``Máire Uí Bhriain`` → family
       ``Uí Bhriain``). ``Nic`` and ``Mic`` are also given names, so
       one opening a name read given-first stays the given name,
       reported. See
       `Packs that choose a language`_.
   * - ``gd``
     - Scottish Gaelic — chooses ``gd``, which turns on ``Nic``
       (``Màiri Nic Leòid`` → family ``Nic Leòid``).
   * - ``hi``
     - Hindi — chooses ``hi``, which turns on the romanized salutations
       ``Smt`` and ``Shrimati`` (Mrs.) and ``Shriyut`` (Mr.), read as
       titles where the default reads a name word (``Shrimati Indira
       Gandhi`` → title ``Shrimati``). ``Shri`` is not among them. See
       :ref:`Romanized Indic titles <romanized-indic-titles>`.
   * - ``ja``
     - Japanese segmentation — activates division for unspaced
       Japanese names, which needs a segmenter to act: install
       ``nameparser[ja]`` and pass
       ``parser_for(locales.JA, segmenter=locales.ja_segmenter())``
       (``山田太郎`` → family ``山田``, given ``太郎``). The pack ships
       no surname list, because no list divides a kanji name, and no
       order: a Japanese name already reads family-first by default.
       The pack also chooses the language ``ja``, which turns on the
       honorific ``君`` (``逢沢　一郎君`` → suffix ``君``), as the Diet
       writes its members. The default leaves it in the name, since
       ``王君`` is a complete Chinese name, so a Chinese name read under
       this pack loses its ``君`` the same way.
   * - ``mn``
     - Mongolian — reads a name written wholly in Cyrillic family first,
       the given name last, so the father's name, which a Mongolian name
       writes first and official records file as the surname, is the
       family (``Батын Сүхээ`` → family ``Батын``, given ``Сүхээ``); a
       romanized name keeps your order. See
       :ref:`Mongolian names <mongolian-names>`.
   * - ``ne``
     - Nepali given names — chooses the language ``ne``, which reads
       ``श्री``, ``गुरु`` and ``Guru`` as name words, placed by position,
       where the default reads them as titles (``श्री कृष्ण श्रेष्ठ`` →
       given ``श्री`` in the default order, where the default gives
       title ``श्री``). Each stays a title inside a title phrase
       (``His Holiness Guru Prasad``). It also turns
       ``initials_as_family`` on, so a surname written as its initials
       is the family (``Ram Bahadur B K`` → family ``B K``, where the
       default gives middle ``Bahadur B``, family ``K``; see
       :ref:`initials-as-family`).
   * - ``pt``
     - Portuguese — chooses ``pt``, which settles Portuguese's clashes
       its way (``do`` a particle, not the DO credential; see
       :ref:`Spanish and Portuguese titles <spanish-portuguese-titles>`).
   * - ``pt_br``
     - Brazilian Portuguese — chooses ``pt-BR``, and with it ``pt``,
       which settles ``pt``'s clashes and turns on ``SB``, the agnomen Sobrinho
       as Brazilian filings abbreviate it, read as a suffix where the name has words to
       spare (``JOSE CARLOS SILVA SB`` → suffix ``SB``), and settles
       Portuguese's clashes its way.
       See `Packs that choose a language`_.
   * - ``ru``
     - East Slavic patronymic order — detects the formal
       family/given/patronymic shape (three name words, the last ending
       like a patronymic — Cyrillic and transliterated
       ``-ovich``/``-ovna``-style endings — the middle not, and no
       initial before the last: ``И. Б. Зубкевич`` keeps family
       ``Зубкевич``) and assigns it accordingly. A middle name with the
       ending fills
       ``patronymic`` too (``Ivan Ivanovich Ivanov`` → middle and
       patronymic ``Ivanovich``).
   * - ``tr_az``
     - Turkic patronymic markers — detects a name of four words ending
       in a standalone marker token (``oglu``, ``qizi``, ``uulu``, and
       their Latin- and Cyrillic-script variants, ``o‘g‘li`` with any
       apostrophe Uzbek text writes) and reads its first
       word as the family name (``Aliyev Ilham Heydar oglu`` → family
       ``Aliyev``). A name of three name words ending in one has no surname,
       so the father's name and the marker are the family
       (``Bekmyrza Cholponbai uulu`` → family ``Cholponbai uulu``). A
       marker and the name before it fill ``patronymic`` (``Heydar
       oglu``, ``Cholponbai uulu``).
   * - ``vi``
     - Vietnamese — reads every name family first, the given name last
       (``Nguyen Van Anh`` → family ``Nguyen``, middle ``Van``, given
       ``Anh``), keeps the syllables other languages read as particles,
       connectives or credentials (``Van``, ``Le``, ``Do``, ``The``,
       and ``CHI`` ending a name in capitals) as name words,
       and chooses ``vi``, which turns on the academic titles written
       before a name that are written as initials too (``TS``, ``GS``,
       ``PGS``) and their stacked forms (``PGS.TS.``). See
       :ref:`Vietnamese names <vietnamese-names>`.
   * - ``zh``
     - Chinese surname segmentation — splits an unspaced Han name into
       surname and given name (``毛泽东`` → family ``毛``, given
       ``泽东``) against the surname list the pack ships. It sets no
       name order: native-script Han already reads family-first
       without a pack. The list holds the commonest surnames of the
       mainland and Taiwan, in both scripts, and the compound surnames
       still borne; a name whose surname is not on it stays whole, and
       a four-character name opening with two of its single surnames
       reads both as the family (``王李小明`` → family ``王李``). A
       Japanese name read with it can split after its first character
       (``安藤一郎`` → family ``安``), so use ``ja`` for Japanese data.

``bn``, ``ga``, ``gd``, ``hi``, ``hr``, ``pt``, ``pt_br`` and ``sl`` are each a choice of languages
and nothing else: the readings each turns on are the default
vocabulary's own, written in its language's file (``ne.toml`` for
Nepali) and off until a caller chooses the language. ``ru`` and
``tr_az`` are policy-only — they carry no vocabulary of their own.
``ne`` is a choice with one policy field beside it,
``initials_as_family``.
``ja`` is a choice of the language ``ja`` (which turns on ``君``) beside one
policy field, the segmentation it needs a segmenter to use.
``es`` and ``es_ar`` are each a choice with a list and one policy field
beside it: each turns ``two_family_names`` on and carries the given
names that switch leaves where they stand. ``cs`` and ``sk`` are a choice with that one policy
field beside it and no list. ``mn`` is a choice with one policy field,
a ``script_orders`` entry for Cyrillic, and its choice turns on nothing. ``vi`` is a choice with one policy field,
``name_order``, and the one fragment that takes readings out rather
than adding them: a choice prefers its language's reading of a word
only where that reading is a title, a particle or another vocabulary
kind, never a name, so no reading ``vi.toml`` could write would keep
``Van`` a name word (its fragment takes out connective and credential
readings of Vietnamese syllables too). ``zh`` is both halves at once: a surname list, plus the
one policy field that turns segmentation on for the script it covers. See
:ref:`config-containers` for how that split (language vocabulary vs. behavior)
is drawn, and :ref:`Contributing a pack to nameparser <contributing-a-pack>` for which half a
new naming rule belongs in.

Under ``ne`` a name opening with one of its words reads it as a name
word, placed by position as any other is, a listed title in front of it
included: the given name in the default order, the family name under a
family-first one.

.. doctest::

    >>> ne = parser_for(locales.NE)
    >>> parse("Guru Prasad Sharma").title
    'Guru'
    >>> guru = ne.parse("Guru Prasad Sharma")
    >>> guru.title, guru.given, guru.family
    ('', 'Guru', 'Sharma')
    >>> ne.parse("Mr. Guru Sharma").given
    'Guru'
    >>> from nameparser import FAMILY_FIRST, Parser, Policy
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> parser_for(locales.NE, base=family_first).parse("Guru Prasad Sharma").family
    'Guru'

The choice reads Hindi and Marathi names too, where ``श्री`` is
usually the salutation (Mr.), so use it for Nepali data.

.. warning::

   A pack declares a name *shape*, not a language (save one that
   chooses languages, such as ``ne``, which names a language yet acts
   on every name holding one of its words, whatever language that name
   is in). Either way, it cannot tell whose name it is looking at. Any surname that happens to end in a
   patronymic suffix matches the East Slavic rule, including names
   that are not East Slavic at all:

   .. doctest::

       >>> ru = parser_for(locales.RU)
       >>> name = ru.parse("David Michael Abramovich")
       >>> name.given, name.family
       ('Michael', 'David')

   The default parser reads that as given ``David``, family
   ``Abramovich``. This is the trade the pack asks you to make, and it
   is why packs are opt-in rather than automatic: enable one only for
   data that is predominantly in the order it detects. If your input
   mixes traditions, parse the subsets separately with different
   parsers rather than enabling a pack over all of it.

A declared family-first ``name_order`` stands down both patronymic
rotations (``ru`` and ``tr_az``) instead of competing with them. Under
``FAMILY_FIRST`` the two never disagree on a name the rule matches: that
order already reads ``"Сидоров Иван Петрович"`` as family ``Сидоров``,
so folding the pack onto a base built with it adds nothing. Under
``FAMILY_FIRST_GIVEN_LAST`` the declared order wins, and the last
word — the patronymic, or a separate ``oglu``/``qizi`` marker — reads
as the given name. ``patronymic`` does not stand down, but it reads only
a middle name with the ending, so it follows the order: under
``FAMILY_FIRST`` ``Ivan Ivanovich Ivanov`` reads given ``Ivanovich``
and no patronymic. A marker and the word before it are read under
every order.

.. _language-packs:

Packs that choose a language
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some words are right in one language and wrong as a default, because
another language written in the same script reads them differently.
Irish writes a woman's surname with ``Nic`` (daughter of) or, married,
``Uí`` (of the descendant of) before it, but ``Nic`` is also the short
form of Nicholas; Brazilian filings abbreviate the agnomen *Sobrinho*
(nephew) to ``SB``, which is also the S.B. degree. The default reads
none of them, and ``ga``, ``gd`` and ``pt_br`` turn them on:

.. doctest::

    >>> parse("Máire Uí Bhriain").family
    'Bhriain'
    >>> parser_for(locales.GA).parse("Máire Uí Bhriain").family
    'Uí Bhriain'
    >>> parse("JOSE CARLOS SILVA SB").family
    'SB'
    >>> brazil = parser_for(locales.PT_BR).parse("JOSE CARLOS SILVA SB")
    >>> brazil.family, brazil.suffix
    ('SILVA', 'SB')

Each word is then read as its language reads the full word: ``SB`` is a
suffix only where the name keeps a family name without it (``Ana SB``
keeps family ``SB``), and in a name read given-first ``Nic`` opening it
stays the given name (``Nic Cage``), as ``Mac`` does by default; under
a family-first order it is the first word, read as the family name.
Each reports its doubt in ``ambiguities``.

``pt`` and ``pt_br`` also turn on a Portuguese given name written
behind a particle that is too rare to read by default (``da
Piedade``), so the phrase reads as a middle name, as ``das Graças``
does by default (see :ref:`two-given-names`):

.. doctest::

    >>> parse("Maria da Piedade Costa").family
    'da Piedade Costa'
    >>> piedade = parser_for(locales.PT).parse("Maria da Piedade Costa")
    >>> piedade.middle, piedade.family
    ('da Piedade', 'Costa')

A choice also settles every clash its language has a reading for, as
`Choosing languages`_ shows, and that costs the other languages'
readings of those words:

- **Under ga and gd,** ``Mc`` is the clan particle, so ``John Smith MC``
  gives family ``MC`` and loses the Military Cross.
- **Under pt and pt_br,** the words read as ``pt`` reads them: ``John
  Smith DO`` gives family ``DO``. ``Sr`` keeps both readings, *Senhor*
  in front and "Senior" behind, as in the default, under ``es`` too.
- **Under pt_br,** a written S.B. degree reads as Sobrinho
  (``Howard Gordon, MD SB`` fills ``generation`` with ``SB``).

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

The lexicon fragment is validated on its own
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``policy`` half is a patch, but the ``lexicon`` half is not. A
pack's :class:`~nameparser.Lexicon` is a complete value in its own
right: its readings are checked as they are added (a phrase, a
``may_be_initial`` on anything but a single cased letter, an agnomen
with no name reading), and again when ``|`` joins them onto the base,
where a reading that clashes with one the base holds raises with the
pack's code. A fragment holding ``Lexicon.empty().add("dc",
kind="generation")`` fails there, ``dc`` being a credential in the
default and a word holding one suffix kind. A reading that marks
another, as a ``given`` reading makes a particle possibly given, needs
nothing else in the fragment: ``Lexicon.empty().add("mc", kind="given")``
marks the base's particle ``mc``. ``zh`` is the shipped worked example:
its ``Lexicon(surnames=...)`` holds a list and no reading. A fragment's
``remove`` calls apply after the choice too, as a caller's own do:
``vi``'s fragment, ``Lexicon.empty().remove("van", ..., kind="particle")``
with a call each for ``kind="conjunction"`` and ``kind="credential"``,
takes out those readings of the syllables it lists, and only those
(``mac`` stays a particle, ``ma`` and ``md`` credentials).
