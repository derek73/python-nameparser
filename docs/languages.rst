Notes by language
=================

This page is the detail behind the :ref:`shipped packs <shipped-packs>`
table: for each language, how its names are written, what the default
reads already, what the pack adds, what it costs and, where that was
measured, how much it gains. :doc:`locales` says how packs and choices
of language work, and lists every pack.

Every pack here is used the same way, folded onto a parser with
:func:`~nameparser.parser_for`: ``parser_for(locales.CS)`` is a parser
for Czech names. A pack is for data that is mostly in its language,
since it cannot tell whose name it is reading
(:ref:`what-a-pack-costs`). Where your data mixes languages, parse each
subset with its own parser, or pass several packs to ``parser_for``:
"Stacking packs" in :doc:`locales` says how they combine, and
:ref:`choosing-languages` what a choice of several languages reads.

The sections below cover Czech, Slovak, Slovenian and Croatian names,
Spanish and Portuguese titles and family names, romanized Indic titles,
Vietnamese, Mongolian and Thai names, and Maghrebi, Amazigh, Hebrew and
Dutch particles. Other languages are described where their mechanism is:

- **East Slavic patronymics** (``ru``): :ref:`east-slavic-patronymics`.
- **Turkic patronymic markers** (``tr_az``):
  :ref:`turkic-patronymic-markers`.
- **Nepali** (``ne``): :ref:`nepali-given-names`.
- **Irish and Scottish Gaelic** (``ga``, ``gd``):
  :ref:`gaelic-clan-particles`.
- **The words the Portuguese packs turn on** (``pt``, ``pt_br``):
  :ref:`portuguese-packs`.
- **Chinese, Japanese and Korean** (``zh``, ``ja``, and Korean with no
  pack): :ref:`east-asian-names`.


.. _west-south-slavic-packs:

Czech, Slovak, Slovenian and Croatian names
-------------------------------------------

Turn on ``cs``, ``sk``, ``sl`` or ``hr`` when your data is names in
that language. Each of the four languages is a pack of its own, which
chooses that one language; the Czech and Slovak packs also read two
family names (`Double surnames`_).

These four languages tell a father from a son of the same name with a
word written after the name: ``ml.`` for the younger and ``st.`` for
the elder (Czech *mladší* and *starší*, Croatian *mlađi* and
*stariji*). Czech and Slovak also write academic degrees as titles
before the name, run together in their own capitalization (``MUDr.``,
``JUDr.``, ``PhDr.``, ``Mgr.``), and a few degrees after it
(``DrSc.``, Slovak ``ArtD.``).

What the default reads and what waits for a pack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default reads the doctorates before the name (``MUDr.``,
``JUDr.``, ``PhDr.``, ``RNDr.`` and the rest), and ``Mgr.``, which it
lists as Monsignor. It cannot read the other words, each of which
another reading claims:

- ``ml.`` is also a pair of initials.
- ``st.`` is Saint in English and French.
- ``Pan`` and ``Roz`` are names in other languages.
- ``MgA.`` and the rank ``mjr.`` (major) are written as initials too.
- ``BcA.`` is an English credential.

So they wait for a pack:

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

.. doctest::

    >>> from nameparser import Lexicon, Locale, Parser, locales, parse, parser_for
    >>> czech = parser_for(locales.CS)
    >>> parse("Jiří Dienstbier ml.").family
    'ml.'
    >>> czech.parse("Jiří Dienstbier ml.").suffix
    'ml.'
    >>> czech.parse("Jana Nováková roz. Svobodová").maiden
    'Svobodová'

Where a title is read, by spelling and position
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whether a degree written as a title is read depends on whether it is
written with its period and on where it stands. The doctorates and
``Mgr.`` read the same with or without ``cs`` or ``sk``. ``MgA.``,
``BcA.`` and ``mjr.``, which the default does not list as titles, are
titles under ``cs`` wherever a doctorate is one:

.. list-table::
   :header-rows: 1
   :widths: 28 18 18 18 18

   * - Written
     - A doctorate, ``Mgr.``
     - ``MgA.``, ``mjr.`` by default
     - ``BcA.`` by default
     - All three under ``cs``
   * - Bare, before the name: ``MgA Jana Malá``
     - title
     - name word
     - name word
     - title
   * - Dotted, before the name: ``MgA. Jana Malá``
     - title
     - title, by its shape
     - title, by its shape
     - title
   * - Bare, after a comma: ``Jana Malá, MgA``
     - title
     - name word
     - suffix
     - title
   * - Dotted, after a comma: ``Jana Malá, MgA.``
     - title
     - title, by its shape
     - suffix
     - title
   * - Dotted, at the end: ``Jana Malá MgA.``
     - title
     - name word
     - suffix
     - title
   * - Bare, at the end: ``Jana Malá MgA``
     - name word
     - name word
     - suffix
     - name word

Written bare at the end of a name, as any title is, a doctorate or
``Mgr.`` is a name word (``Jan Novák MUDr`` → family ``MUDr``), and so
are ``MgA``, ``BcA`` and ``mjr`` under ``cs``. "By its shape" is the
default's reading of any unlisted abbreviation written with a period
at the head of a name or of the part after a comma (see
:ref:`abbreviated-titles`).

.. doctest::

    >>> parse("Jan Novák, MUDr").title
    'MUDr'
    >>> parse("Jana Malá, MgA").family
    'Jana Malá'
    >>> czech.parse("Jana Malá, MgA").title
    'MgA'
    >>> parse("Jana Malá, BcA").suffix
    'BcA'
    >>> czech.parse("Jana Malá, BcA").title
    'BcA'

Double surnames
~~~~~~~~~~~~~~~

A Czech or Slovak woman who keeps her own surname beside her
husband's writes the two without a hyphen, ``Alena Pešová Řehořová``,
which the default reads as a middle name and a family name. The two
packs read two family names (``two_family_names``, see
:ref:`two-family-names`), so the double surname stays whole, each
name in its own view (``surname1`` ``Pešová``, ``surname2``
``Řehořová``).

Two given names pay for it: with no Czech or Slovak given-name list to
keep a given name out of the family (none is published for the whole
population), ``Petr Pavel Novák`` reads family ``Pavel Novák``. A family
comma keeps both as the default reads them:

.. doctest::

    >>> czech.parse("Alena Pešová Řehořová").family
    'Pešová Řehořová'
    >>> czech.parse("Petr Pavel Novák").family
    'Pavel Novák'
    >>> czech.parse("Novák, Petr Pavel").middle
    'Pavel'

The switch gains more names than it costs (`Measured effect: Czech and
Slovak`_). To keep the packs' vocabulary and turn the switch off,
rebuild the policy:

.. doctest::

    >>> import dataclasses
    >>> one_family = Parser(lexicon=czech.lexicon, policy=dataclasses.replace(
    ...     czech.policy, two_family_names=False))
    >>> one_family.parse("Petr Pavel Novák").family
    'Novák'

Stacking with another pack
~~~~~~~~~~~~~~~~~~~~~~~~~~

Stacked with another pack, the switch reads that pack's names too:

- **With locales.RU,** a patronymic written after the given name joins
  the family (``Ivan Petrovich Sidorov`` → family ``Petrovich
  Sidorov``, where ``locales.RU`` alone reads the patronymic
  ``Petrovich``), as it does where ``locales.RU`` is stacked with
  ``locales.ES``.
- **With locales.ES,** the Spanish given-name list is applied to Czech
  and Slovak names and keeps the given names it holds out of the
  family, many of them names borne in both countries (``Jan``,
  ``Marie``, ``Anna``).

.. doctest::

    >>> parser_for(locales.CS, locales.RU).parse("Ivan Petrovich Sidorov").family
    'Petrovich Sidorov'
    >>> czech.parse("Jan Marie Novák").family
    'Marie Novák'
    >>> parser_for(locales.CS, locales.ES).parse("Jan Marie Novák").family
    'Novák'

What choosing the language costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Choosing the language costs the other readings of the words it turns
on:

- **Under cs,** ``Pan Wei`` reads title ``Pan``, and ``Rosalind Roz
  Smith`` takes ``Smith`` for a maiden name.
- **Under all four packs,** ``st`` loses its Saint readings, so ``St
  Clair Smith`` reads given ``St``.

A caller whose names also hold the English Saint chooses French too, a
choice that changes no other word:

.. doctest::

    >>> czech.parse("St Clair Smith").given
    'St'
    >>> french = Locale(code="fr", lexicon=Lexicon.empty(),
    ...                 languages=frozenset({"fr"}))
    >>> parser_for(locales.CS, french).parse("St Clair Smith").title
    'St'

A word's :attr:`~nameparser.Reading.languages` names the files whose
reading is on under the parser's choice (see :ref:`reading-taken`), so
it shows which reading a word took. ``ml.`` under the Czech choice
names ``cs``, and so does ``Mgr.``, the choice having dropped the
Monsignor reading of ``en`` and ``fr``, which the default names:

.. doctest::

    >>> czech.parse("Jiří Dienstbier ml.").tokens[-1].reading.languages
    ('cs',)
    >>> parse("Mgr. Jan Novák").tokens[0].reading.languages
    ('en', 'fr')
    >>> czech.parse("Mgr. Jan Novák").tokens[0].reading.languages
    ('cs',)

Measured effect: Czech and Slovak
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Among ORCID's researchers, who split their own names into a given and
a family box, reading two family names raises the names agreeing in
both from 95.0% to 96.4% in Czechia and from 94.8% to 96.4% in
Slovakia. Among the candidates of the 2022 municipal and 2025 Chamber
elections, about 170,000 records, each a distinct set of the boxes the
Czech registers file a name in, it raises them from 97.0% to 97.5%.
The Spanish given-name list carried beside ``locales.CS`` moved fewer
than two hundred of those register records, about seven in ten of them
to agreeing. The
dated figures are in
``docs/design/decisions/O6-two-family-names.md`` and
``docs/design/decisions/vocabulary-model.md``.


.. _spanish-portuguese-titles:

Spanish and Portuguese titles
-----------------------------

Turn on ``es`` when your data is Spanish names, ``es_ar`` when it is
Argentine ones, and ``pt`` when it is Portuguese ones. The default
already reads the titles described below, save two that ``es`` turns
on; the larger change is two family names, which the Spanish packs
read and ``pt`` leaves off.

Titles
~~~~~~

Spanish and Latin American usage puts an academic or professional title
in front of a name (*Licenciado*, *Ingeniero*, *Mtro.*), and Portuguese
does the same with *Doutor* and *Professora*. These words are borne
as names hardly at all, so the default reads them as titles, written
out, abbreviated or dotted. A family name that is one of them, opening
a name written family name first without a comma, reads as the title
too (``Doctora Ruiz Ana`` → title ``Doctora``): ``Doctora``,
``Licenciado`` and ``Lic`` are each a family name almost nowhere in
ORCID or PatentsView (``docs/design/decisions/vocabulary-model.md``,
:issue:`1115`).

``es`` turns on the two titles the default leaves off: ``Maestra``,
which is also a family name and the word for a schoolteacher, and
``Doña``, a family name too.

.. doctest::

    >>> parse("Lic Juan Pérez").title
    'Lic'
    >>> parse("Maestra Ana Ruiz").given
    'Maestra'
    >>> spanish = parser_for(locales.ES).parse("Maestra Ana Ruiz")
    >>> spanish.title, spanish.given
    ('Maestra', 'Ana')

Some words stay name words under the packs:

- ``Don``, ``Dona`` and ``Dom``: names open with each as a given name
  more often than as the title, Spanish and Portuguese data included.
- ``Maestro``, a Spanish family name, though ``Maestra`` is a title
  under ``es`` (``Maestra Ana Ruiz Paz`` → title ``Maestra``).
- An office written before a name with its complement (``Ministro de
  Hacienda Juan Pérez``). Names are written that way so rarely that
  the packs leave it alone.

A particle behind a title starts the family as it does by default
(``Doctora de la Vega`` → family ``de la Vega``).

Two family names under ``es``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``es`` reads a name as Spanish names are written, with two family
names, the father's and then the mother's (``two_family_names``, see
:ref:`two-family-names`). It carries a list of 1,000 Spanish given
names, the ones INE's 2025 census tables count as given names in at
least 90% of their uses, so a given name standing before the family
stays out of it:

.. doctest::

    >>> parse("Gabriel García Márquez").family
    'Márquez'
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

A compound given name stays opt-in under the Spanish packs and ``pt``
alike (``two_given_names``, see :ref:`two-given-names`): people filling
a form with a middle-name box put the second given name there.

.. _argentine-spanish-pack:

Argentina: ``es_ar``
~~~~~~~~~~~~~~~~~~~~

Turn on ``es_ar`` in place of ``es`` for Argentine names. Two family
names are less settled in Argentina than in Spain and most of Latin
America, and many of its commonest second given names, ``Sebastián``,
``Nicolás``, ``Matías``, ``Andrés``, are given names Spain also bears
as surnames in a fifth to a quarter of their uses. So ``es``'s list,
which keeps only words given in at least 90% of their uses, leaves
them out and the switch takes them into the family.

``es_ar`` is ``es`` with about 5,000 given names from the same census
tables, the ones counted as given names in at least half their uses:

.. doctest::

    >>> argentina = parser_for(locales.ES_AR)
    >>> spain.parse("Pablo Sebastián Rosales").family
    'Sebastián Rosales'
    >>> argentina.parse("Pablo Sebastián Rosales").family
    'Rosales'
    >>> argentina.parse("Gabriel García Márquez").family
    'García Márquez'

A word Spain bears mostly as a surname, ``Martín``, ``Esteban``, is on
neither list, so the switch still takes it. Choosing ``es`` and
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
reads fewer researchers' names right than ``es``'s does.

.. _portuguese-two-family-names:

Portuguese: why ``pt`` leaves the switch off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Where reading two family names helps your Portuguese data, turn it on
beside the pack, on the base parser:

.. doctest::

    >>> from nameparser import Policy
    >>> parser_for(locales.PT).parse("Tiago Barros Queiroz").family
    'Queiroz'
    >>> pt_two = parser_for(locales.PT,
    ...                     base=Parser(policy=Policy(two_family_names=True)))
    >>> pt_two.parse("Tiago Barros Queiroz").family
    'Barros Queiroz'

``pt`` does not turn it on, because it serves every
Portuguese-speaking country and the switch helps some and sinks
others: among ORCID's researchers it mends about two names for each it
breaks in Portugal (71.5% → 83.2%) and three in Brazil (49.5% →
74.4%), but sinks Angola (75.9% → 57.3%) and Mozambique (85.2% →
50.2%), and a Portuguese given-name list to guard it does not exist
yet.

Whether it helps Portuguese or Brazilian data depends on who split the
names: it gains on names their bearers split themselves, as ORCID's
are, and costs about 5 points on names filed through a form, as the UK
company register's Portuguese filers are (61.1% → 56.1%).
:ref:`portuguese-packs` says what ``pt`` and ``pt_br`` do turn on.

Measured effect: Spanish
~~~~~~~~~~~~~~~~~~~~~~~~

The figures are of ORCID's researchers, who split their own names into
a given and a family box, and count the names that agree in every box
with the filer:

- **Under es, outside Argentina,** each country of one measurement
  gains (Spain, Mexico, Colombia, Peru, Chile, Venezuela, Ecuador,
  Bolivia, Cuba and Uruguay): by default they read between 13.5%
  (Peru) and 61.8% (Uruguay) of names right, and under the pack
  between 93.2% (Venezuela) and 97.3% (Chile).
- **In Argentina,** 83.4% by default, 90.2% under ``es`` and 96.1%
  under ``es_ar``. Among Argentine inventors on US patents the figures
  are 93.8% by default, 86.2% under ``es`` and 92.7% under ``es_ar``,
  since most of them write one family name. The Argentine figures
  are from a separate, later measurement, which leaves out the records
  whose given box opens with a title.

The dated figures, and those for Portuguese above, are in
``docs/design/decisions/O6-two-family-names.md``; the Argentine ones
are from its entry on ``locales.ES_AR``.


.. _romanized-indic-titles:

Romanized Indic titles
----------------------

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
----------------

Turn on ``vi`` when your data is Vietnamese names, and only then: it
reads every name of two words or more family name first, unless a
comma marks the family name.

A Vietnamese name is written family name first, then the middle name,
then the given name, and the default, reading given-first, reads it the
other way round, diacritics or none. ``vi`` does four things:

- It reads the name in its own order.
- It keeps syllables such as ``Van`` (Văn), ``Le`` (Lê), ``Do`` (Đỗ)
  and ``The`` (Thế) as name words where other languages' particles and
  connectives would join them to the words beside them.
- It keeps ``Chi``, ``Ba`` and ``Do`` from being read as a credential
  ending a name written in capitals (``NGUYEN LINH CHI``).
- It reads the academic titles written before a name.

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

What the pack does to other names:

- **Keep it for Vietnamese data.** The order holds for every name of
  two words or more the pack reads without a family comma:
  ``vietnamese.parse("John Smith")`` gives family ``John``.
- **One-word names.** A one-word name reads as the given name, the name
  a Vietnamese person goes by, as it does under every order
  (``Policy.lone_name_word``, see :ref:`lone-name-word`).
- **After a family comma.** A family comma fixes the family name
  whatever the order, and the part after it reads given-first, as under
  every order (``Nguyen, Van Anh`` → family ``Nguyen``, given ``Van``,
  middle ``Anh``), so ``Smith, John`` reads under ``vi`` as it does by
  default. The syllables ``vi`` keeps as name words are name words
  there too (``Beethoven, Ludwig van`` gives middle ``van``).
- **DO, BA and CHI after the name.** ``DO`` or ``BA`` written after a
  Vietnamese name as a credential, for English-language readers, reads
  as a name word, with a comma or without (``Nguyen Van Anh, DO`` gives
  family ``Nguyen Van Anh``, given ``DO``). So does ``CHI`` without a
  comma, or in a name written wholly in capitals (``NGUYEN VAN ANH,
  CHI`` gives given ``CHI``). Other credentials, and ``CHI`` in
  capitals after a comma in a name written in mixed case, stay
  suffixes (``Nguyen Van Anh, PhD``).

.. doctest::

    >>> vietnamese.parse("John Smith").family
    'John'
    >>> vietnamese.parse("Beethoven, Ludwig van").middle
    'van'
    >>> vietnamese.parse("Nguyen Van Anh, DO").given
    'DO'
    >>> vietnamese.parse("Nguyen Van Anh, CHI").suffix
    'CHI'
    >>> vietnamese.parse("Nguyen Van Anh, PhD").suffix
    'PhD'


.. _mongolian-names:

Mongolian names
---------------

A Mongolian name has no inherited family name. It is the father's name
(rarely the mother's), then the given name, the name a person goes by.
Written in full the father's name is in the genitive (``Батын Сүхээ``,
"Sükhee, Bat's"); passports write it in the nominative (``Бат Сүхээ``)
and put it in the surname field. The default reads the father's name as
the given name; ``mn`` reads it as the family, the field a caller sorts
and matches by, in a name written in Cyrillic:

.. doctest::

    >>> parse("Батын Сүхээ").given
    'Батын'
    >>> mongolian = parser_for(locales.MN)
    >>> sukhee = mongolian.parse("Батын Сүхээ")
    >>> sukhee.family, sukhee.given
    ('Батын', 'Сүхээ')
    >>> mongolian.parse("Б. Сүхээ").family
    'Б.'

The order is keyed to the script. Mongolians writing their own names in
Latin letters mostly put the given name first, so a romanized name keeps
your order (``Policy.name_order``, given-first by default), and for a
list written the other way, declare ``FAMILY_FIRST`` on the base parser
or let :ref:`Parser.suggest <suggest-settings>` read it:

.. doctest::

    >>> mongolian.parse("Sükhee Batyn").given
    'Sükhee'

Cyrillic is written for many languages in both orders, so the pack reads
every name written wholly in Cyrillic father's name first, Russian and
Kazakh names included (``mongolian.parse("Иван Сидоров")`` gives family
``Иван``): keep it for Mongolian data. A family comma fixes the family
name whatever the order (``Бат, Сүхээ``), a one-word name reads as the
given name, and the genitive ending is not read, so ``patronymic`` stays
empty. A word written before the father's name, a clan name, reads as the
family, the father's name as the middle.

Mongolian names are often written short, with the father's name as an
initial (``Б. Сүхээ``). Under the pack that initial is the family, so a
matcher built from it reads the pair as a family written with an
initial, ``family-initial``, which no matcher accepts unless asked, and
calls the two spellings inconsistent. The default matcher calls them
consistent only because it reads the father's name as the given name.
Accept ``family-initial`` to match them under the pack:

.. doctest::

    >>> mongolian.matching().check("Батын Сүхээ", "Б. Сүхээ")["family"].outcome.value
    'family-initial'
    >>> plain = mongolian.matching()
    >>> mongolian.matching(accept=plain.accept | {"family-initial"}).check(
    ...     "Батын Сүхээ", "Б. Сүхээ").consistent
    True


.. _thai-names:

Thai names
----------

A Thai name written in Thai script needs no pack and no setting: its
titles, the noble particle ``ณ`` and the absence of initials are read
by default. A Thai name written in Latin letters gets none of this
(`Where the Thai reading stops`_).

A person is addressed in Thai by the given name after any title, and
the examples here write the given name first, then the family name,
the order the default reads.

Titles stand before the name: the salutations ``นาย`` (Mr.), ``นาง`` (Mrs.) and
``นางสาว`` (Miss), academic and professional titles, military and
police ranks, and royal lineage titles. A title is written out
(``รองศาสตราจารย์``, associate professor) or short with full stops
(``รศ.``), and it is often glued to the given name with no space; the
salutations are glued more often than written apart. Thai does not
write names as initials. A few noble family names open with the
particle ``ณ`` (``ณ อยุธยา``).

Thai script sets no order of its own, so the examples below are read
given name first, the default. A parser set to a family-first order
(:ref:`name-order`) reads Thai names family name first too, and so
does one built from a pack that sets that order: under
``parser_for(locales.VI)`` (:ref:`vietnamese-names`), ``นายสมชาย ใจดี``
gives given ``ใจดี``, family ``สมชาย``. A choice of other languages
keeps the Thai titles, ``ณ`` and the split.

Titles glued to the given name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A salutation or a spelled-out title glued to the start of the name's
first word is split off and read as the title. The name without it
reads the same either way:

.. doctest::

    >>> parse("สมชาย ใจดี").given
    'สมชาย'
    >>> somchai = parse("นายสมชาย ใจดี")
    >>> somchai.title, somchai.given, somchai.family
    ('นาย', 'สมชาย', 'ใจดี')
    >>> parse("นางสุดา ใจดี").title
    'นาง'
    >>> thai_miss = parse("นางสาวสุดา ใจดี")
    >>> thai_miss.title, thai_miss.given
    ('นางสาว', 'สุดา')
    >>> thai_ajarn = parse("อาจารย์สุดา ใจดี")
    >>> thai_ajarn.title, thai_ajarn.given
    ('อาจารย์', 'สุดา')

The longest listed title is the one taken, so ``นางสาวสุดา`` is Miss
Suda and not Mrs. ``สาวสุดา``. Where the longer title would leave a
vowel sign with no consonant to sit on, the shorter one is taken
instead:

.. doctest::

    >>> thai_sawitri = parse("นางสาวิตรี ใจดี")
    >>> thai_sawitri.title, thai_sawitri.given
    ('นาง', 'สาวิตรี')

A title written apart reads the same as one glued (``นาย สมชาย ใจดี``
gives title ``นาย``), and several written apart are all read.

Titles written short, ranks and royal titles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A listed title written short with its full stops is read glued to the
name's first word or apart, alone or in a chain:

.. doctest::

    >>> thai_dr = parse("ดร.สุดา ใจดี")
    >>> thai_dr.title, thai_dr.given
    ('ดร.', 'สุดา')
    >>> thai_chain = parse("รศ.ดร.สุดา ใจดี")
    >>> thai_chain.title, thai_chain.given
    ('รศ.ดร.', 'สุดา')
    >>> parse("รองศาสตราจารย์ ดร.สุดา ใจดี").title
    'รองศาสตราจารย์ ดร.'

Military and police ranks are read written out or short, feminine
forms among them (``พ.อ.หญิง``), and so are the royal lineage titles
(``หม่อมราชวงศ์``, short ``ม.ร.ว.``):

.. doctest::

    >>> thai_rank = parse("พ.ต.ท.สมชาย ใจดี")
    >>> thai_rank.title, thai_rank.given
    ('พ.ต.ท.', 'สมชาย')
    >>> parse("พันตำรวจโทสมชาย ใจดี").title
    'พันตำรวจโท'
    >>> thai_royal = parse("หม่อมราชวงศ์สมชาย ใจดี")
    >>> thai_royal.title, thai_royal.given
    ('หม่อมราชวงศ์', 'สมชาย')
    >>> parse("ม.ร.ว.สมชาย ใจดี").title
    'ม.ร.ว.'

A title before one name word
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After a title, one name word is read as the family name in most
languages (``Dr. Smith``). After a listed Thai title it is the given name,
since that is the name a Thai title is used with. ``ว่าที่`` (acting) is
the exception: it is a modifier, a title only before a rank, and alone
before a name word it is read as a given name.

.. doctest::

    >>> parse("Dr. Smith").family
    'Smith'
    >>> parse("ดร. สุดา").given
    'สุดา'
    >>> parse("นายสมชาย").given
    'สมชาย'

Family names that open with ``ณ``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ณ`` is read as a particle, so in a name read given name first it
and the word after it are one family name:

.. doctest::

    >>> thai_noble = parse("นางสาวสุดา ณ อยุธยา")
    >>> thai_noble.given, thai_noble.middle, thai_noble.family
    ('สุดา', '', 'ณ อยุธยา')

Opening a name read given name first, ``ณ`` takes the rest of the
name into the family name (``ณ อยุธยา สุดา``), as ``de`` does. Under a
family-first order the pair is placed as that order places its words,
and a ``ณ`` standing alone is a given name.

Initials
~~~~~~~~

:meth:`~nameparser.ParsedName.initials`, with its default ``spec``,
gives an empty string for a name in Thai script (a ``spec`` of your
own keeps its literal characters), as it does for Chinese, Japanese
and Korean ones,
since Thai does not write names as initials. A word in another script
beside it still gives its own:

.. doctest::

    >>> parse("Somchai Jaidee").initials()
    'S. J.'
    >>> parse("สมชาย ใจดี").initials()
    ''
    >>> parse("สมชาย Jaidee").initials()
    'J.'

Where the Thai reading stops
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are left as written:

- **A short title glued with no full stop at all.** ``ดร``, ``นพ`` and
  the other short forms written without stops stay part of the given
  name when nothing separates them from it, because Thai given names
  open with the same letters (``นพพร``, ``นพดล``). With the full stop,
  or a space, they are read
  (``docs/design/decisions/W6-glued-title-peel.md``, :issue:`317`).
- **A dotted short form missing its last full stop.** A short form
  with stops inside it needs its last one too. Glued without it, a
  form of two parts stays in the given name
  (``พ.ตสมชาย``), and a longer one is cut at its last stop:
  ``พ.ต.ทสมชาย`` reads the shorter rank ``พ.ต.``, and ``ม.ร.วสมชาย``,
  where no shorter title is listed, reads given ``ม.ร.`` and middle
  ``วสมชาย``.
- **Two spelled-out titles glued together.** Only the first is split
  off, and the second stays in the given name. Both are read where one
  of them is written short with its full stops (``รศ.นายแพทย์สมชาย``,
  ``รองศาสตราจารย์ดร.สุดา``), or where a space stands between them.
- **A short academic title glued after a family comma.** After a comma
  that marks the family name, a word such as ``ดร.สุดา`` is kept whole
  and read as the title, as is a glued chain that holds such a title
  (``นายดร.สุดา``), and a word after it is then the given name
  (``ใจดี, ดร.สุดา ศรี`` gives given ``ศรี``). Written apart it
  divides. Any other listed title glued alone, spelled out or short, is
  split off there as elsewhere (``ใจดี, อาจารย์สุดา``,
  ``ใจดี, ม.ร.ว.สมชาย``).
- **A zero-width joiner after the title.** A zero-width joiner or
  non-joiner (U+200D, U+200C) between a glued title and the name stops
  the split. A zero-width space or a no-break space there does not.
- **A word the vocabulary does not list.** ``คุณ`` (Khun) and ``พระ``
  are not titles by default, each also opening ordinary names. A
  caller adds one (`Adding a Thai title`_).
- **A clan name before** ``ณ อยุธยา``. A royal clan's surname written
  between the given name and ``ณ อยุธยา`` is read as a middle name,
  the parser reading by position.
- **Latin letters.** Nothing is split off a name written wholly in
  Latin letters, and the romanized particle ``na`` is not read, being
  also a Korean family name. ``Mr.`` is read as it is in any name;
  ``Khun`` is not listed and reads as the given name.

.. doctest::

    >>> parse("ดรสุดา ใจดี").given
    'ดรสุดา'
    >>> thai_cut = parse("พ.ต.ทสมชาย ใจดี")
    >>> thai_cut.title, thai_cut.given
    ('พ.ต.', 'ทสมชาย')
    >>> thai_mrw = parse("ม.ร.วสมชาย ใจดี")
    >>> thai_mrw.title, thai_mrw.given, thai_mrw.middle
    ('', 'ม.ร.', 'วสมชาย')
    >>> parse("นาย\u200dสมชาย ใจดี").title
    ''
    >>> thai_comma = parse("ใจดี, ดร.สุดา")
    >>> thai_comma.title, thai_comma.given
    ('ดร.สุดา', '')
    >>> parse("ใจดี, ดร. สุดา").given
    'สุดา'
    >>> parse("ใจดี, นายสมชาย").given
    'สมชาย'
    >>> thai_two = parse("รองศาสตราจารย์นายแพทย์สมชาย ใจดี")
    >>> thai_two.title, thai_two.given
    ('รองศาสตราจารย์', 'นายแพทย์สมชาย')
    >>> parse("รองศาสตราจารย์ นายแพทย์สมชาย ใจดี").title
    'รองศาสตราจารย์ นายแพทย์'
    >>> parse("รองศาสตราจารย์ดร.สุดา ใจดี").title
    'รองศาสตราจารย์ดร.'
    >>> parse("ปฐมพร อินทรางกูร ณ อยุธยา").middle
    'อินทรางกูร'
    >>> parse("Suda na Ayutthaya").family
    'Ayutthaya'
    >>> parse("Mr. Somchai Jaidee").title
    'Mr.'
    >>> thai_khun = parse("Khun Somchai Jaidee")
    >>> thai_khun.given, thai_khun.middle
    ('Khun', 'Somchai')

Adding a Thai title
~~~~~~~~~~~~~~~~~~~

There is no Thai pack, and the readings above need none. A title the
default lacks is added to a :class:`~nameparser.Lexicon`
(:ref:`vocabulary-lexicon`):

.. doctest::

    >>> parse("คุณ สมชาย ใจดี").given
    'คุณ'
    >>> with_khun = Parser(lexicon=Lexicon.default().add(
    ...     "คุณ", kind="title", addresses="given"))
    >>> khun_apart = with_khun.parse("คุณ สมชาย ใจดี")
    >>> khun_apart.title, khun_apart.given
    ('คุณ', 'สมชาย')
    >>> with_khun.parse("คุณ สมชาย").given
    'สมชาย'
    >>> with_khun.parse("คุณสมชาย ใจดี").given
    'คุณสมชาย'

``addresses="given"`` makes the title read as the shipped Thai ones
do, one name word after it being the given name. The added title is
read written apart. Glued, it stays in the given
name unless it is added with ``attached="before"``, which is for a
word that opens no name; ``คุณ`` opens several given names.

Listing the Thai titles
~~~~~~~~~~~~~~~~~~~~~~~

The vocabulary holds about two hundred Thai titles, most of them
ranks. :meth:`~nameparser.Lexicon.words` lists them by kind,
``"salutation"``, ``"academic"``, ``"military"`` or ``"nobility"``,
each stored without its last full stop:

.. doctest::

    >>> thai_salutations = [
    ...     word for word in Lexicon.default().words(kind="salutation")
    ...     if "฀" <= word[0] <= "๿"]
    >>> sorted(thai_salutations)
    ['ด.ช', 'ด.ญ', 'น.ส', 'นาง', 'นางสาว', 'นาย', 'เด็กชาย', 'เด็กหญิง']


.. _maghrebi-hebrew-particles:

Maghrebi, Amazigh and Hebrew particles
--------------------------------------

Turn on ``locales.AR`` or ``locales.HE`` when your data holds Tunisian
or Israeli family names written with ``Ben`` in Latin letters. The
other particles described here, and ``בן`` in Hebrew script, are read
by default.

Read by default: ``Ait``, ``Ould``, ``El``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Family names in Morocco, Algeria, Tunisia and Mauritania, written in
French spelling, often open with a word that joins the next one: the
Amazigh ``Ait`` and ``Nait`` ("the people of"), the Hassaniya ``Ould``
("son of"), ``Ouled`` ("children of", in Algerian and Moroccan family
names), and ``El``, the article ``al`` as
Morocco, Algeria and Egypt spell it. The default reads each as part of the
family name, and ``Ould``, with which a Mauritanian name still forms the
father's name, fills ``patronymic`` too:

.. doctest::

    >>> parse("Youssef Ait Haddou").family
    'Ait Haddou'
    >>> parse("Sara El Haddou").family
    'El Haddou'
    >>> haddou = parse("Ahmed Ould Haddou")
    >>> haddou.family, haddou.patronymic
    ('Ould Haddou', 'Ould Haddou')

``El`` has two limits:

- **Opening a name.** ``El``, like ``Al``, is also a given name where
  it opens one (``El Mehdi``), so there it stays the given name and
  reports the fork.
- **Inside a compound given name.** A compound given name written with
  ``El`` inside it, as Algerian names are, gives the article and the
  rest to the family name (``Nour El Houda Haddou`` gives family ``El
  Houda Haddou``). Among ORCID's Algerian researchers ``El`` read this
  way breaks between three and four names for each it fixes, where in
  Morocco, Egypt and Lebanon it fixes more than ten for each it breaks
  (``docs/design/decisions/vocabulary-collisions.md``, :issue:`1257`).

A listing written family name first without a comma reads whole as the
family name (``Ait Haddou Karim``), as one opening with ``de`` does;
write the comma or declare the order.

``Ben``: the Arabic and Hebrew packs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Ben`` ("son of") opens Tunisian and Israeli family names the same way
(``Ben Haddad``), but it is also the given name Ben, and a British
middle name, standing where the particle would claim it, so the default
leaves it to position. The Arabic and Hebrew packs, ``locales.AR`` and
``locales.HE``, each choose their one language and read it as the
family name:

.. doctest::

    >>> parse("Karim Ben Haddad").family
    'Haddad'
    >>> arabic = parser_for(locales.AR)
    >>> arabic.parse("Karim Ben Haddad").family
    'Ben Haddad'
    >>> arabic.parse("Ben Haddad").given
    'Ben'

A ``Ben`` opening a name stays the given name and reports the fork,
save under a strict Arabic choice (``strict=True``), which drops
English's given name Ben and reads a leading ``Ben`` as the family
name.

What the packs cost
~~~~~~~~~~~~~~~~~~~

- **A chain of fathers' names.** The packs are for family names written
  with ``Ben``, not for a civil register's chain of fathers' names:
  ``Karim ben Ali ben Salah Haddad`` gives middle ``ben Ali``, family
  ``ben Salah Haddad`` under either pack, where the default keeps the
  chain in the middle name and reads the family right (a Tunisian
  register-style list read nearly nine names in ten right by default
  and fewer than one in six with ``ben`` read, :issue:`1248`).
- **The credential ABD, under locales.AR.** Choosing Arabic costs
  English's reading of ``abd``, which Arabic reads as a given name
  (``Abd Rahman``), so the credential ABD (All But Dissertation) is a
  name word under ``locales.AR``: ``Jane Smith, ABD`` gives given
  ``ABD``, family ``Jane Smith``. Choose ``en`` too to keep it.
- **Ait and Nait, under a strict Arabic choice.** A strict Arabic
  choice also drops the Amazigh ``Ait`` and ``Nait``, which are
  ``ber``'s (Berber), so for Moroccan and Algerian data choose ``ber``
  too.
- **Other languages' particles, under a strict Hebrew choice.** A
  strict Hebrew choice keeps ``Ben`` and the particles written in
  Hebrew script, and drops the particles of other languages written in
  Latin letters, ``Ait``, ``Nait``, ``Ould``, ``Ouled`` and ``El``
  among them (``Sara El Haddou`` gives middle ``El``).

.. doctest::

    >>> english = Locale(code="en", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"en"}))
    >>> parser_for(locales.AR, english).parse("Jane Smith, ABD").suffix
    'ABD'
    >>> parser_for(locales.AR, strict=True).parse("Youssef Ait Haddou").family
    'Haddou'
    >>> berber = Locale(code="ber", lexicon=Lexicon.empty(),
    ...                 languages=frozenset({"ber"}))
    >>> parser_for(locales.AR, berber, strict=True).parse(
    ...     "Youssef Ait Haddou").family
    'Ait Haddou'

Hebrew script
~~~~~~~~~~~~~

In Hebrew script ``בן`` is read by default: opening a name it is the
given name Ben, the fork reported, and inside a name it starts the
family name, which it does not fill ``patronymic`` with, since the
Israeli family names written with it name no father. ``אבו`` and ``אל``,
the Arabic ``Abu`` and ``al-`` that Arab citizens of Israel write in
Hebrew script, read as their Latin spellings do:

.. doctest::

    >>> parse("בן כהן").given
    'בן'
    >>> parse("יעל בן חיים").family
    'בן חיים'
    >>> parse("סאמי אבו חליל").family
    'אבו חליל'

Under a family-first order (``Policy(name_order=FAMILY_FIRST)``), a
family name written with ``בן`` first and no comma gives ``בן`` alone
to the family and reports the fork (``בן חיים יעל`` gives family ``בן``,
given ``חיים``): write the comma (``בן חיים, יעל``) to keep it whole.

An Arab name written in Hebrew with ``בן`` for the father therefore
leaves ``patronymic`` empty, and a given name written with ``אל``
inside it (``עבד אל עזיז``, Abd al-Aziz) gives the article and the rest
to the family name.

Measured effect: ``Ben``
~~~~~~~~~~~~~~~~~~~~~~~~

Among ORCID's researchers, who split their own names into a given and a
family box, the names agreeing in both boxes rise from 87.6% by default
to 96.1% under either pack in Tunisia, and from 92.7% to 93.5% in
Israel. The dated figures are in
``docs/design/decisions/vocabulary-collisions.md``.

.. _dutch-particles:

Dutch particles
---------------

Turn on ``locales.NL`` when your data is Dutch or Flemish names written
with ``ten``, the one particle the pack adds. The other Dutch particles
the vocabulary lists are read by default; one it does not list, such as
the ``in`` of ``in 't Veld``, is added as :ref:`adding-a-word` shows.

Read by default: ``van``, ``de``, ``ter``, ``Oude``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Dutch family name often opens with prepositions and articles written
in lower case (``van der Berg``, ``ter Horst``, ``'t Hooft``). The
default reads them as part of the family name, and reads ``Oude``
("old") the same way, which opens the farm names of Twente and the
Achterhoek and is written with a capital (``Oude Luttikhuis``):

.. doctest::

    >>> parse("Jan van der Berg").family
    'van der Berg'
    >>> luttikhuis = parse("PIET OUDE LUTTIKHUIS")
    >>> luttikhuis.family, str(luttikhuis.capitalized())
    ('OUDE LUTTIKHUIS', 'Piet Oude Luttikhuis')

``Oude`` is also a rare Dutch given name, so where it opens a name it
stays the given name and reports the fork, as ``van`` does.

``ten``: the Dutch pack
~~~~~~~~~~~~~~~~~~~~~~~

``ten`` ("at the") opens family names the same way (``ten Brink``), but
it is also a syllable of Chinese given names, written between two words
(``Kheng Ten Choo``), where the particle would take it into the family
name. So the default leaves it to position, and ``locales.NL``, which
chooses Dutch, reads it as the start of the family name:

.. doctest::

    >>> parse("Jan ten Brink").family
    'Brink'
    >>> dutch = parser_for(locales.NL)
    >>> dutch.parse("Jan ten Brink").family
    'ten Brink'
    >>> dutch.parse("Ten Brink").given
    'Ten'

Under the pack, a ``Ten`` opening a name stays the given name and
reports the fork, save under a strict Dutch choice (``strict=True``), which drops the
Chinese given name and reads a leading ``Ten`` as the family name.

What the pack costs
~~~~~~~~~~~~~~~~~~~

- **A Chinese given-name syllable inside a name.** ``Kheng Ten Choo``
  gives family ``Ten Choo`` under the pack. Among ORCID's,
  PatentsView's and the UK company register's records, ``ten`` read as
  a particle fixes 86 names for 9 it breaks, 66 to 4 among Dutch
  records, and two of the breaks are names of this shape
  (``docs/design/decisions/vocabulary-collisions.md``, :issue:`1455`).
- **Two particle runs.** A family name of two Dutch names, each opening
  with a particle, keeps only the second as the family name when the
  second opens with ``ten`` (``Jutte van der Werff ten Bosch`` gives
  middle ``van der Werff``, family ``ten Bosch``), as one whose second
  name opens with ``ter`` does by default.
- **The credential VD.** Choosing Dutch costs English's reading of
  ``vd``, which Dutch reads as ``van der`` written short, so the
  credential VD (the Volunteer Decoration) is a name word under
  ``locales.NL``: ``John Smith VD`` gives family ``VD``, and ``John
  Smith, VD`` reads whole as the family name. Choose ``en`` too to keep
  it.
- **A leading Ten, under a strict Dutch choice.** A strict Dutch
  choice drops the Chinese given name, so a ``Ten`` opening the name,
  or opening the given name after a family comma, joins the family
  (``Brink, Ten Jan`` gives family ``Brink Ten Jan``).
- **Other languages' particles, under a strict Dutch choice.** A
  strict Dutch choice drops the particles of other languages written in
  Latin letters (``Maria da Silva`` gives middle ``da``).

.. doctest::

    >>> english = Locale(code="en", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"en"}))
    >>> parser_for(locales.NL, english).parse("John Smith VD").suffix
    'VD'
