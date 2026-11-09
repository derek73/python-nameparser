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
and ``sk`` may read any name of three words differently, and ``vi``,
whose name order is its shape, any name: the order moves every name a
family comma does not fix, and its titles and its removed readings
reach the comma names too. The warning
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

Two East Asian behaviors are on by default for the same reason, except
that what selects them is the *script* rather than the word
(:ref:`east-asian-defaults` covers turning them off). The background
(covered fully under :ref:`east-asian-names`): Chinese, Japanese, and Korean names put the family name
first in native script and are usually written with no space between
the parts. Both defaults follow from facts the script alone
establishes. A name written wholly in Han or Hangul — or in kanji and
kana other than katakana alone, which only Japanese produces — is assigned
family-first, because every language written in those scripts orders
names that way; no language guess is involved. An unspaced hangul
name is additionally split into surname and given name, because hangul
is written by nothing but Korean and Korean surnames are a closed
census set that ships as default vocabulary. Splitting an unspaced
*Han* name is the one behavior the script cannot license — the same
characters could be a Chinese or a Japanese name, and a Chinese
surname list splits Japanese names in the wrong place — so it is not a
default: the ``zh`` and ``ja`` packs below turn it on for data whose
language you can declare.

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
  (``hu``, whose file records only words kept out and familiar forms,
  which only name matching reads) raises ``ValueError``, a plain choice
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
  letters, only the shared ones, and keeps ``hu.toml``'s familiar
  forms, which name matching reads, dropping every other file's.
- **Your own words stay.** A word a strict choice drops is kept where
  you added it yourself, your lexicon's readings applying after the
  choice (`Your own words outrank a choice`_).

.. _west-south-slavic-packs:

Czech, Slovak, Slovenian and Croatian names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These four languages tell a father from a son of the same name with a
word written after the name: ``ml.`` for the younger and ``st.`` for
the elder (Czech *mladší* and *starší*, Croatian *mlađi* and
*stariji*). Czech and Slovak also write academic degrees as titles
before the name, run together in their own capitalization (``MUDr.``,
``JUDr.``, ``PhDr.``, ``Mgr.``), and a few degrees after it
(``DrSc.``, Slovak ``ArtD.``). The default reads the doctorates
before the name, but cannot read the other words: ``ml.`` is also a
pair of initials, ``st.`` is Saint in English and French, ``Pan`` and
``Roz`` are names in other languages, ``MgA.`` and the rank ``mjr.``
(major) are written as initials too and ``BcA.`` is an English
credential. So they wait for a pack,
and each of the
four languages is a pack of its own, which chooses that one language;
the Czech and Slovak packs also read two family names (below):

.. list-table::
   :header-rows: 1

   * - Pack
     - Turns on
   * - ``locales.CS``
     - ``ml.``, ``st.``; the titles ``MgA.``, ``BcA.`` and ``mjr.``, and
       ``Mgr.`` read as the degree; ``DrSc.``
       after the name; ``Pan`` (Mr.); ``roz.``, which routes a maiden
       name as ``rozená`` does; two family names
       (``two_family_names``)
   * - ``locales.SK``
     - ``ml.``, ``st.``; ``Mgr.`` read as the degree;
       ``ArtD.`` and ``DrSc.`` after the name; two family names
       (``two_family_names``)
   * - ``locales.SL``, ``locales.HR``
     - ``ml.``, ``st.``

The doctorates (``MUDr.``, ``JUDr.``, ``PhDr.``, ``RNDr.`` and the
rest) are titles without a pack, bare or dotted before the name or
after a comma, and dotted at the end of it, and so is ``Mgr.``, which
the default lists as Monsignor; written bare at the end of a name, as
any title is, each is a name word (``Jan Novák MUDr`` → family
``MUDr``). For ``MgA.``, ``BcA.`` and ``mjr.``, which the default does not list,
what a pack changes is the bare spelling before the name or after a
comma, and the dotted one at the end of it, where the default reads
each as a name word; at the head of a name the dotted spelling is a
title by its shape without one.

.. doctest::

    >>> czech = parser_for(locales.CS)
    >>> parse("Jiří Dienstbier ml.").family
    'ml.'
    >>> czech.parse("Jiří Dienstbier ml.").suffix
    'ml.'
    >>> parse("Jan Novák, MUDr").title
    'MUDr'
    >>> parse("Jana Malá, MgA").family
    'Jana Malá'
    >>> czech.parse("Jana Malá, MgA").title
    'MgA'
    >>> czech.parse("Jana Nováková roz. Svobodová").maiden
    'Svobodová'

A word's :attr:`~nameparser.Reading.languages` names the files whose
reading is on under the parser's choice: ``ml.`` above names ``cs``,
whose reading the choice turns on, and ``Mgr.`` names ``cs`` alone, the
Czech choice having dropped the Monsignor reading of ``en`` and ``fr``
for its own, which the default names:

.. doctest::

    >>> czech.parse("Jiří Dienstbier ml.").tokens[-1].reading.languages
    ('cs',)
    >>> parse("Mgr. Jan Novák").tokens[0].reading.languages
    ('en', 'fr')
    >>> czech.parse("Mgr. Jan Novák").tokens[0].reading.languages
    ('cs',)

A Czech or Slovak woman who keeps her own surname beside her
husband's writes the two without a hyphen, ``Alena Pešová Řehořová``,
which the default reads as a middle name and a family name. The two
packs read two family names (``two_family_names``, see
:ref:`two-family-names`), so the double surname stays whole, each
name in its own view (``surname1`` ``Pešová``, ``surname2``
``Řehořová``). Two given
names pay for it: with no Czech or Slovak given-name list to keep a
given name out of the family (none is published for the whole
population), ``Petr Pavel Novák`` reads family ``Pavel Novák``. A family
comma keeps both as the default reads them:

.. doctest::

    >>> czech.parse("Alena Pešová Řehořová").family
    'Pešová Řehořová'
    >>> czech.parse("Petr Pavel Novák").family
    'Pavel Novák'
    >>> czech.parse("Novák, Petr Pavel").middle
    'Pavel'

It gains more names than it costs. Among ORCID's researchers, who split
their own names into a given and a family box, the names agreeing in
both rise from 95.0% to 96.4% in Czechia and from 94.8% to 96.4% in
Slovakia; among the 170,181 records of the 2022 municipal and 2025
Chamber elections' candidates, each a distinct set of the boxes the
Czech registers file a name in, from 97.0% to 97.5% (measured
2026-10-30). To keep the packs' vocabulary and
turn the switch off, rebuild the policy:

.. doctest::

    >>> import dataclasses
    >>> one_family = Parser(lexicon=czech.lexicon, policy=dataclasses.replace(
    ...     czech.policy, two_family_names=False))
    >>> one_family.parse("Petr Pavel Novák").family
    'Novák'

Stacked with another pack, the switch reads that pack's names too.
With ``locales.RU`` a patronymic written after the given name joins the
family (``Ivan Petrovich Sidorov`` → family ``Petrovich Sidorov``, where
``locales.RU`` alone reads the patronymic ``Petrovich``), as it does
stacked with ``locales.ES``. With ``locales.ES``, the Spanish given-name
list is applied to Czech and Slovak names and keeps the given names it
holds out of the family, many of them names borne in both countries
(``Jan``, ``Marie``, ``Anna``): over the Czech registers it moved 186
records against ``locales.CS`` alone, 134 of them to agreeing (measured
2026-10-30).

.. doctest::

    >>> parser_for(locales.CS, locales.RU).parse("Ivan Petrovich Sidorov").family
    'Petrovich Sidorov'

Choosing the language costs the other readings of these words. ``Pan
Wei`` reads title ``Pan``, ``Rosalind Roz Smith`` takes ``Smith`` for
a maiden name, and ``st`` loses its Saint readings, so ``St Clair
Smith`` reads given ``St``. A caller whose names also hold the English
Saint chooses French too, a choice that changes no other word:

.. doctest::

    >>> czech.parse("St Clair Smith").given
    'St'
    >>> french = Locale(code="fr", lexicon=Lexicon.empty(),
    ...                 languages=frozenset({"fr"}))
    >>> parser_for(locales.CS, french).parse("St Clair Smith").title
    'St'

Finding packs by code
~~~~~~~~~~~~~~~~~~~~~

Find what's shipped with :func:`~nameparser.locales.available`, and
look one up dynamically by its lowercase code with
:func:`~nameparser.locales.get`:

.. doctest::

    >>> locales.available()
    ('bn', 'cs', 'es', 'es_ar', 'ga', 'gd', 'hi', 'hr', 'ja', 'ne', 'pt', 'pt_br', 'ru', 'sk', 'sl', 'tr_az', 'vi', 'zh')
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
       `Romanized Indic titles`_.
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
       ``Pérez``). See `Spanish and Portuguese titles`_.
   * - ``es_ar``
     - Argentine Spanish — ``es`` with a longer given-name list, one
       holding given names that Spain bears often enough as surnames
       to leave off ``es``'s list, which Argentine names write before a
       single surname (``Pablo Sebastián
       Rosales`` → family ``Rosales``, where ``es`` gives ``Sebastián
       Rosales``). See `Spanish and Portuguese titles`_.
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
       `Romanized Indic titles`_.
   * - ``ja``
     - Japanese segmentation — activates division for unspaced
       Japanese names, which needs a segmenter to act: install
       ``nameparser[ja]`` and pass
       ``parser_for(locales.JA, segmenter=locales.ja_segmenter())``
       (``山田太郎`` → family ``山田``, given ``太郎``). The pack ships
       no surname list, because no list divides a kanji name, and no
       order: a Japanese name already reads family-first by default.
   * - ``ne``
     - Nepali given names — chooses the language ``ne``, which reads
       ``श्री``, ``गुरु`` and ``Guru`` as name words, placed by position,
       where the default reads them as titles (``श्री कृष्ण श्रेष्ठ`` →
       given ``श्री`` in the default order, where the default gives
       title ``श्री``). Each stays a title inside a title phrase
       (``His Holiness Guru Prasad``).
   * - ``pt``
     - Portuguese — chooses ``pt``, which settles Portuguese's clashes
       its way (``do`` a particle, not the DO credential; see
       `Spanish and Portuguese titles`_).
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
       ``-ovich``/``-ovna``-style endings — and the middle not) and
       assigns it accordingly. A middle name with the ending fills
       ``patronymic`` too (``Ivan Ivanovich Ivanov`` → middle and
       patronymic ``Ivanovich``).
   * - ``tr_az``
     - Turkic patronymic markers — detects a name of four words ending
       in a standalone marker token (``oglu``, ``qizi``, ``uulu``, and
       their Latin- and Cyrillic-script variants) and reads its first
       word as the family name (``Aliyev Ilham Heydar oglu`` → family
       ``Aliyev``). A marker and the name before it fill
       ``patronymic`` (``Heydar oglu`` there).
   * - ``vi``
     - Vietnamese — reads every name family first, the given name last
       (``Nguyen Van Anh`` → family ``Nguyen``, middle ``Van``, given
       ``Anh``), keeps the syllables other languages read as particles,
       connectives or credentials (``Van``, ``Le``, ``Do``, ``The``,
       and ``CHI`` ending a name in capitals) as name words,
       and chooses ``vi``, which turns on the academic titles written
       before a name that are written as initials too (``TS``, ``GS``,
       ``PGS``) and their stacked forms (``PGS.TS.``). See
       `Vietnamese names`_.
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

``bn``, ``ga``, ``gd``, ``hi``, ``hr``, ``ne``, ``pt``, ``pt_br`` and ``sl`` are each a choice of languages
and nothing else: the readings each turns on are the default
vocabulary's own, written in its language's file (``ne.toml`` for
Nepali) and off until a caller chooses the language. ``ja``, ``ru`` and
``tr_az`` are policy-only — they carry no vocabulary of their own.
``es`` and ``es_ar`` are each a choice with a list and one policy field
beside it: each turns ``two_family_names`` on and carries the given
names that switch leaves where they stand. ``cs`` and ``sk`` are a choice with that one policy
field beside it and no list. ``vi`` is a choice with one policy field,
``name_order``, and the one fragment that takes readings out rather
than adding them: a choice prefers its language's reading of a word
only where that reading is a title, a particle or another vocabulary
kind, never a name, so no reading ``vi.toml`` could write would keep
``Van`` a name word (its fragment takes out connective and credential
readings of Vietnamese syllables too). ``zh`` is both halves at once: a surname list, plus the
one policy field that turns segmentation on for the script it covers. See
:ref:`config-containers` for how that split (language vocabulary vs. behavior)
is drawn, and `Contributing a pack to nameparser`_ for which half a
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

.. _spanish-portuguese-titles:

Spanish and Portuguese titles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Spanish and Latin American usage puts an academic or professional title
in front of a name (*Licenciado*, *Ingeniero*, *Mtro.*), and Portuguese
does the same with *Doutor* and *Professora*. These words are borne
as names hardly at all, so the default reads them as titles, written
out, abbreviated or dotted; a family name written first that is one
(``Doctora``, ``Licenciado`` and ``Lic`` are each borne once in ORCID
or PatentsView) reads as the title. ``es`` turns on the two it leaves off, ``Maestra``, which is
also a family name and the word for a schoolteacher, and ``Doña``, a
family name too:

.. doctest::

    >>> parse("Lic Juan Pérez").title
    'Lic'
    >>> parse("Maestra Ana Ruiz").given
    'Maestra'
    >>> spanish = parser_for(locales.ES).parse("Maestra Ana Ruiz")
    >>> spanish.title, spanish.given
    ('Maestra', 'Ana')

``Don``, ``Dona`` and ``Dom`` are not among them: names open with each
as a given name more often than as the title, Spanish and Portuguese
data included. Nor is ``Maestro``, a Spanish family name, though
``Maestra`` is (``Maestra Ana Ruiz Paz`` → title ``Maestra``). An office written before a name with its complement
(``Ministro de Hacienda Juan Pérez``) is not read either. Names are
written that way so rarely that the packs leave it alone, and a
particle behind a title starts the family as it does by default
(``Doctora de la Vega`` → family ``de la Vega``).

``es`` also reads a name as Spanish names are written, with two family
names, the father's and then the mother's (``two_family_names``, see
:ref:`two-family-names`). It carries a list of 1,000 Spanish given
names, the ones INE's 2025 census tables count as given names in at
least 90% of their uses, so a given name standing before the family
stays out of it:

.. doctest::

    >>> spain = parser_for(locales.ES)
    >>> spain.parse("Gabriel García Márquez").family
    'García Márquez'
    >>> spain.parse("José Luis Pérez").family
    'Pérez'

``family`` keeps both names, and the parse gives each its own view:
``surname1`` and ``surname2``, with ``surname1_base`` for filing by
the first surname without its particles (see :ref:`aggregate-views`):

.. doctest::

    >>> marquez_es = spain.parse("Gabriel García Márquez")
    >>> marquez_es.surname1, marquez_es.surname2
    ('García', 'Márquez')
    >>> vega_es = spain.parse("Juan de la Vega del Valle")
    >>> vega_es.surname1, vega_es.surname1_base
    ('de la Vega', 'Vega')

Data from systems without the letter ñ writes ``Begoña`` as
``Begona``, so each listed name written with ñ is listed with n too,
where that spelling is still mostly a given name. A name written with ñ
is never taken for one written with n: ``Oña`` is a surname, though
``Ona`` is a listed given name.

.. doctest::

    >>> spain.parse("Maria Begona Lopez").family
    'Lopez'
    >>> spain.parse("Juan Oña Pérez").family
    'Oña Pérez'

Among ORCID's researchers in the 11 Spanish-speaking countries
measured, the names that agree in every box with the filer rise from
13.5% (Peru) to 82.5% (Argentina) by default to 89.3% (Argentina) to
97.3% (Chile) under the pack (measured 2026-10-30).

Two family names are less settled in Argentina than in Spain and most
of Latin America, and many of its commonest second given names, ``Sebastián``, ``Nicolás``,
``Matías``, ``Andrés``, are given names Spain also bears as surnames
in a fifth to a quarter of their uses, so ``es``'s list, which keeps
only words given in at least 90% of their uses, leaves them out and the
switch takes them into the family.
``es_ar`` is ``es`` with 5,000 given names from the same census tables,
the ones counted as given names in at least half their uses:

.. doctest::

    >>> argentina = parser_for(locales.ES_AR)
    >>> spain.parse("Pablo Sebastián Rosales").family
    'Sebastián Rosales'
    >>> argentina.parse("Pablo Sebastián Rosales").family
    'Rosales'
    >>> argentina.parse("Gabriel García Márquez").family
    'García Márquez'

Measured again on 2026-11-04, after later changes to the parser and
without the records whose given box opens with a title, the Argentine
researchers' names that agree in every box rise from 83.4% by default
and 90.2% under ``es`` to 96.1% under ``es_ar``; among Argentine inventors on US patents, 93.8% by
default, 86.2% under ``es`` and 92.7% under ``es_ar``, since most of
them write one family name. A word Spain bears mostly as a surname,
``Martín``, ``Esteban``, is on neither list, so the switch still takes
it. Choosing ``es`` and
``es_ar`` together reads as ``es_ar``.

The longer list costs a name written with two family names whose first
family name is on it. ``Santiago`` is a given name in 57% of its uses
in Spain, so ``es_ar`` lists it and reads it as a middle name, where
``es`` keeps both family names:

.. doctest::

    >>> spain.parse("Carlos Santiago López").family
    'Santiago López'
    >>> argentina.parse("Carlos Santiago López").family
    'López'

That cost is why ``es`` keeps its shorter list: in Spain, Mexico,
Peru, Bolivia, Ecuador, Costa Rica, Guatemala, Cuba, the Dominican
Republic and Puerto Rico, the longer list
reads fewer researchers' names right than ``es``'s does (measured
2026-11-04).

A compound given name stays opt-in
(``two_given_names``): people filling a form with a middle-name box put
the second given name there. ``pt`` turns neither switch on, because it serves every
Portuguese-speaking country: among ORCID's researchers the switch
mends about two names for each it breaks in Portugal (71.5% → 83.2%)
and three in Brazil (49.5% → 74.4%), but sinks Angola (75.9% → 57.3%)
and Mozambique (85.2% → 50.2%), and a Portuguese given-name list to
guard it does not exist yet. Whether it helps Portuguese or Brazilian
data depends on who split the names: it gains on names their bearers
split themselves, as ORCID's are, and costs about 5 points on names
filed through a form, as the UK company register's Portuguese filers
are (61.1% → 56.1%). Where it helps your data, turn it on beside the
pack: ``parser_for(locales.PT,
base=Parser(policy=Policy(two_family_names=True)))``.

Romanized Indic titles
^^^^^^^^^^^^^^^^^^^^^^

The default reads the Devanagari and Bengali salutations as titles
(``श्रीमती``, ``শ্রীমতী``), since no Latin name is spelled in those
scripts, and leaves their romanizations to position, since a Latin
spelling can be a name. ``hi`` and ``bn`` turn on the romanized forms
whose leading use is the title:

.. doctest::

    >>> parse("Smt Nirmala Sitharaman").given
    'Smt'
    >>> hindi = parser_for(locales.HI).parse("Smt Nirmala Sitharaman")
    >>> hindi.title, hindi.given
    ('Smt', 'Nirmala')
    >>> parser_for(locales.BN).parse("Adhyapak Anisuzzaman Khan").title
    'Adhyapak'

Two are left out, because the names that open with them outnumber the
titles even in Indian data. ``Shri`` opens a given name written in two
words (``Shri Kant``, ``Shri Lakshmi``), and ``Sushri`` an Odia one
(``Sushri Sangita``), so both stay name words under the packs. A strict
Hindi choice, which reads no Odia names, reads ``Sushri`` as the title:

.. doctest::

    >>> parser_for(locales.HI).parse("Sushri Sangita Behera").given
    'Sushri'
    >>> parser_for(locales.HI, strict=True).parse("Sushri Sangita Behera").title
    'Sushri'

``Smt.`` and ``Shri.`` written with their period are titles at the head
of a name by default, packs or no. ``Pandit``, ``Sardar``, ``Kumari``,
``Babu``, ``Acharya`` and ``Begum`` are titles under no pack: each opens
far more names as a given name or a surname than as the title.

.. _vietnamese-names:

Vietnamese names
^^^^^^^^^^^^^^^^

A Vietnamese name is written family name first, then the middle name,
then the given name, and the default, reading given-first, reads it the
other way round, diacritics or none. ``vi`` reads it in its own order,
keeps syllables such as ``Van`` (Văn), ``Le`` (Lê), ``Do`` (Đỗ) and ``The`` (Thế) as name
words where other languages' particles and connectives would join them
to the words beside them, keeps ``Chi``, ``Ba`` and ``Do`` from being
read as a credential ending a name written in capitals
(``NGUYEN LINH CHI``), and reads the academic titles written before a
name:

.. doctest::

    >>> parse("Nguyen Van Anh").given
    'Nguyen'
    >>> vietnamese = parser_for(locales.VI)
    >>> anh = vietnamese.parse("Nguyen Van Anh")
    >>> anh.family, anh.middle, anh.given
    ('Nguyen', 'Van', 'Anh')
    >>> vietnamese.parse("Lê Thị Mai").family
    'Lê'
    >>> vietnamese.parse("PGS.TS. Nguyen Van Anh").title
    'PGS.TS.'

The order holds for every name of two words or more the pack reads
without a family comma, so keep it for Vietnamese data:
``vietnamese.parse("John Smith")`` gives family ``John``. A one-word
name reads as the given name, the name a Vietnamese person goes by, as
it does under every order (``Policy.lone_name_word``, see
:ref:`lone-name-word`). A family
comma fixes the family name whatever the order, and the part after it
reads given-first, as under every order (``Nguyen, Van Anh`` → family
``Nguyen``, given ``Van``, middle ``Anh``), so ``Smith, John`` reads
under ``vi`` as it does by default; but the syllables ``vi`` keeps as
name words are name words there too (``Beethoven, Ludwig van`` gives
middle ``van``). ``DO`` or ``BA`` written after a Vietnamese name as a
credential, for English-language readers, reads as a name word, with a
comma or without (``Nguyen Van Anh, DO`` gives family ``Nguyen Van
Anh``, given ``DO``), and ``CHI`` without a comma or in a name written
wholly in capitals (``NGUYEN VAN ANH, CHI`` gives given ``CHI``); other
credentials, and ``CHI`` after a comma in a name written in mixed case,
stay suffixes (``Nguyen Van Anh, PhD``).

.. _segmenter-contract:

Segmenters
-----------

``ja`` is policy-only in a second sense: it turns division on for
Japanese text without supplying anything to divide with. That job goes
to a **segmenter**, which is passed to
:func:`~nameparser.parser_for` rather than carried by the pack — a
:class:`~nameparser.Locale` is pure data, and a third-party callable is
neither pure nor data. :func:`~nameparser.locales.ja_segmenter` is the
shipped one; writing your own is worth it for any script whose
divisions you know better than a surname list does.

A :data:`~nameparser.Segmenter` is any callable taking a token's text
and returning a :class:`~nameparser.Segmentation` — the interior
offsets to cut at, plus how confident you are — or ``None`` to decline,
leaving the token whole. Declining is the load-bearing half of the
contract, because ``segment_scripts`` unions across packs: your
segmenter may be offered a token of any activated script, not only the
ones its own pack turned on. It is asked only where the surname list
could not divide an unspaced token, and not where the name is already
divided — by a second word in an East Asian script (the nakaguro ・
counts as a space), a family comma or a 间隔号. A word in any other
script beside the token — Latin (``"Dr. 高橋一郎"``), Cyrillic — divides
nothing, so the segmenter is still asked. Halfwidth katakana counts as
katakana, so ``"高橋一郎 ﾀﾛｳ"`` is already divided. Recognize the text
you can actually read and return ``None`` for the rest, rather than
answering for a script you never meant to handle. A segmenter is your
code, so its failures do not stay inside the parse: its own exceptions
propagate out of ``parse()``, and an answer of the wrong type or a cut
outside the token raises ``TypeError`` or ``ValueError``.

The pack half of that arrangement carries no words at all, which makes
it the shortest kind of pack there is:

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, Script
    >>> script_pack = Locale(code="myscript", lexicon=Lexicon.empty(),
    ...               policy=PolicyPatch(
    ...                   segment_scripts=frozenset({Script.HAN})))

``nameparser/locales/ja.py`` is the shipped example of exactly that
shape: activation is the pack's entire contribution. Applied without a
segmenter it divides nothing, and building the parser emits a
``UserWarning`` naming the scripts that can never divide and the
argument to pass.

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

Contributing a pack to nameparser
----------------------------------

Shipping a pack in nameparser itself (rather than keeping it local to
your own code) means meeting the in-repo contract, checked mechanically
by ``tests/v2/test_locales.py``:

#. Add a registry entry in ``nameparser/locales/__init__.py`` — a
   ``"CODE": ("module.path", "ATTR")`` row in ``_REGISTRY``, so the
   pack loads lazily on first access (importing ``nameparser.locales``
   never imports pack modules).
#. Write the rules the pack turns on as data, if they are ``Policy``
   fields the vocabulary files' ``[rules]`` table lists
   (``patronymic_rules``, ``name_order``, ``two_family_names``,
   ``two_given_names``): put the
   table in the pack's language file, list the file in ``PACK_RULES``
   in ``tools/vocab/build.py``, rebuild, and give the pack
   ``policy=rules_patch("<tag>")`` from ``nameparser._locale``, as
   ``ru``, ``tr_az``, ``es``, ``cs``, ``sk`` and ``vi`` do. ``nameparser/vocab/README.md``'s "Rules"
   section lists the keys. A rule the table does not list is a change
   to the parser, not to a pack.
#. Declare a module-level ``DEVIATES(name)`` predicate. Given a name
   string, ``DEVIATES`` returns whether *this pack alone* might parse
   it differently from the default parser. Over-declaring is safe; under-declaring is
   not — when in doubt, ``DEVIATES`` should say yes. A pack whose
   scope is a *script* builds the predicate with ``_script_matcher``
   from ``nameparser/_policy.py``, the way ``zh`` and ``ja`` do —
   never by compiling its own character ranges: the factory's
   docstring explains how the pack-contract test enforces this. A
   pack's choice of languages is never declared: its deviations are
   derived from the words the choice changes, so a pack that is nothing
   but a choice (``ne``, ``sl``, ``ga``) declares no ``DEVIATES`` — the
   contract test refuses one, and refuses a choice that changes no
   word — and one with a fragment or a patch beside its choice
   declares only what those change.
#. Add a rotator list to ``tests/v2/test_locales.py``. Every pack needs
   one, but what it has to contain follows from how the pack declares
   its scope:

   - **By marker regex** (``ru``, ``tr_az``): at least one name
     exercising every alternation branch of every regex it defines —
     ``test_rotators_cover_every_marker_branch`` fails until each
     branch is hit.
   - **By codepoint range** (``zh``, ``ja``): there are no branches to
     sweep, so the pack drops out of that test and its rotators carry
     the same weight by hand — the unspaced names the pack must split,
     one per shape of the vocabulary it ships: single surname, compound
     surname, and any spelling variant it means to cover.
   - **By a choice of languages** (``ne``, ``hi``, ``bn``, ``cs``, ``sk``,
     ``sl``, ``hr``, ``ga``, ``gd``, ``es``, ``es_ar``, ``pt``, ``pt_br``, ``vi``): a name for each word the choice changes, in each script it
     is written in and each position where the default reads it
     otherwise — ``test_choice_rotators_cover_every_changed_word`` fails
     until every word is held.
   - **With no vocabulary at all**: list the shapes its *segmenter* must
     divide instead, and mark the rotator tests to skip when the
     optional dependency is absent, so the contract tests still run
     everywhere.
#. Keep the non-interference gate green over the shared corpus plus
   your rotators: every name the packed parser parses differently from
   the default must be one your ``DEVIATES`` predicate flags — no
   silent, undeclared side effects on names outside the pack's stated
   scope.
#. Decide which layer the vocabulary belongs in, if the pack carries
   any. Vocabulary that is *self-selecting* — able to match only text of
   the tradition it came from, the way a hangul surname can only ever
   match hangul — is default-safe, and belongs in the default lexicon
   (``nameparser/vocab/*.toml``; a segmentation surname list such as
   the Korean one, in ``nameparser/config/_ko_surnames.py``, is read as
   ``Lexicon.default().surnames``) rather than in
   a pack: a pack nobody knows
   to ask for is vocabulary nobody gets. Vocabulary that *declares a
   language its script does not* — a Chinese surname list, which
   silently mangles the Japanese names written in the same characters
   — belongs in the pack, where asking for it is the declaration.
   ``ja``, ``ru`` and ``tr_az`` need no vocabulary at all and ship an
   empty :class:`~nameparser.Lexicon`; ``nameparser/locales/zh.py`` is
   the template for one that does.
#. Curate vocabulary conservatively, the same rule as
   :ref:`ambiguous-words`: when you're unsure whether a word or a
   marker belongs, leave it out.

``nameparser/locales/ru.py`` is the reference implementation for a
policy-only pack, ``nameparser/locales/zh.py`` for one that carries
vocabulary, and ``nameparser/locales/ja.py`` for one whose whole
contribution is turning a stage on.
