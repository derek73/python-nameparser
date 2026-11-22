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
Vietnamese, Mongolian and Thai names, Arabic-script names, Maghrebi,
Amazigh, Hebrew and Dutch particles, French ``dit`` names, and Burmese and Malay names. Other languages are described where their mechanism is:

- **East Slavic patronymics** (``ru``): :ref:`east-slavic-patronymics`.
- **Turkic patronymic markers** (``tr_az``):
  :ref:`turkic-patronymic-markers`.
- **Nepali** (``ne``): :ref:`nepali-given-names`.
- **Irish and Scottish Gaelic** (``ga``, ``gd``):
  :ref:`gaelic-clan-particles`.
- **The words the Portuguese packs turn on** (``pt``, ``pt_br``,
  ``pt_pt``): :ref:`portuguese-packs`.
- **Chinese, Japanese and Korean** (``zh``, ``ja``, and Korean with no
  pack): :ref:`east-asian-names`.


.. _west-south-slavic-packs:

Czech, Slovak, Slovenian and Croatian names
-------------------------------------------

Turn on ``cs``, ``sk``, ``sl`` or ``hr`` when your data is names in
that language. Each of the four languages is a pack of its own, which
chooses that one language, and reads two family names (`Double
surnames`_).

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
``JUDr.``, ``PhDr.``, ``RNDr.`` and the rest), ``Mgr.``, which it
lists as Monsignor, and the degrees after it, ``DrSc.`` and ``ArtD.``,
and ``DiS.`` after a comma (``Jan Novák, DiS.``); ``DiS.``, a surname
too, ending a name without a comma stays a name word. It cannot read
the other words, each of which
another reading claims:

- ``ml.`` is also a pair of initials.
- ``st.`` is Saint in English and French.
- ``Pan`` and ``Roz`` are names in other languages.
- ``MgA.`` and the rank ``mjr.`` (major) are written as initials too.
- ``BcA.`` is an English credential, and ``Bc`` the US nursing
  credential BC and a pair of initials.
- ``Ing`` is a given name too (Chinese, Malaysian and Swedish). Written
  with its period ``Ing.`` is a title before the name by its shape, as
  ``Bc.`` is, but not two of them joined by ``et`` (``Ing. et Ing.``).

So they wait for a pack:

.. list-table::
   :header-rows: 1

   * - Pack
     - Turns on
   * - ``locales.CS``
     - ``ml.``, ``st.``; the titles ``MgA.``, ``BcA.``, ``Bc.``, ``Ing.``
       and ``mjr.``, and ``Mgr.`` read as the degree, written bare or
       joined by ``et``; ``Pan`` (Mr.); ``roz.``, which routes a maiden
       name as ``rozená`` does; two family names
       (``two_family_names``)
   * - ``locales.SK``
     - ``ml.``, ``st.``; ``Mgr.`` read as the degree; two family names
       (``two_family_names``)
   * - ``locales.SL``, ``locales.HR``
     - ``ml.``, ``st.``; two family names (``two_family_names``)

.. doctest::

    >>> from nameparser import Lexicon, Locale, Parser, locales, parse, parser_for
    >>> czech = parser_for(locales.CS)
    >>> parse("Jiří Dienstbier ml.").family
    'ml.'
    >>> czech.parse("Jiří Dienstbier ml.").suffix
    'ml.'
    >>> czech.parse("Jana Nováková roz. Svobodová").maiden
    'Svobodová'
    >>> parse("Ing. et Ing. Jan Novák").given
    'Ing. et Ing.'
    >>> czech.parse("Ing. et Ing. Jan Novák").title
    'Ing. et Ing.'

The Czech pack reads ``Ing`` as a title wherever a title is read
before the name, so a name that opens with the given name Ing reads it
as the title under the pack (``Ing Wei Lim`` gives title ``Ing``), as
does Ing alone after a family comma (``Lim, Ing``) and Ing the surname
at the head of one (``Ing Ho, Mei`` gives family ``Ho``); Ing the
surname at the end keeps its place (``Tom Ing`` gives family ``Ing``),
and after a full name and a comma Ing is still the credential. ``BC`` after a comma is
the title too, so initials written there lose their given name
(``MOSS, BC`` gives title ``BC``).

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
     - suffix, by its mixed case (``MgA``, see
       :ref:`all-caps-credentials`); name word (``mjr``)
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
    >>> parse("Jana Malá, MgA").suffix
    'MgA'
    >>> parse("Jana Malá, mjr").family
    'Jana Malá'
    >>> czech.parse("Jana Malá, MgA").title
    'MgA'
    >>> parse("Jana Malá, BcA").suffix
    'BcA'
    >>> czech.parse("Jana Malá, BcA").title
    'BcA'

Double surnames
~~~~~~~~~~~~~~~

A Czech, Slovak, Slovenian or Croatian woman who keeps her own surname
beside her husband's writes the two without a hyphen, ``Alena Pešová
Řehořová``, which the default reads as a middle name and a family name.
The four packs read two family names (``two_family_names``, see
:ref:`two-family-names`), so the double surname stays whole, each
name in its own view (``surname1`` ``Pešová``, ``surname2``
``Řehořová``).

Two given names pay for it: no given-name list ships for these four
languages to keep a given name out of the family, so ``Petr Pavel
Novák`` reads family ``Pavel
Novák``. A family comma keeps both as the default reads them, and an
initial written between the given name and the surname stays the
middle name:

.. doctest::

    >>> czech.parse("Alena Pešová Řehořová").family
    'Pešová Řehořová'
    >>> croatian = parser_for(locales.HR)
    >>> croatian.parse("Ana Puž Kukuljan").family
    'Puž Kukuljan'
    >>> czech.parse("Petr Pavel Novák").family
    'Pavel Novák'
    >>> czech.parse("Novák, Petr Pavel").middle
    'Pavel'
    >>> croatian.parse("Ana M. Kukuljan").middle
    'M.'

The switch gains more names than it costs (`Measured effect`_). To keep the packs' vocabulary and turn the switch off,
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
choice that changes no other word but ``dit`` and ``dite``
(:ref:`french-dit-names`):

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

Measured effect
~~~~~~~~~~~~~~~

Among ORCID's researchers, who split their own names into a given and
a family box, reading two family names raises the names agreeing in
both from 95.0% to 96.4% in Czechia and from 94.8% to 96.4% in
Slovakia. Among the candidates of the 2022 municipal and 2025 Chamber
elections, about 170,000 records, each a distinct set of the boxes the
Czech registers file a name in, it raises them from 97.0% to 97.5%.
The Spanish given-name list carried beside ``locales.CS`` moved fewer
than two hundred of those register records, about seven in ten of them
to agreeing.

For Croatian and Slovenian names it raises ORCID's agreeing names from
88.4% to 98.5% in Croatia and from 90.4% to 97.6% in Slovenia, and the
members of the Croatian Sabor and the Slovenian National Assembly whose
family name it reads right from 140 to 148 of 149 and from 84 to 89 of
90, the one loss in each a member with two given names. Among US
patents' inventors, whose boxes a professional filer fills, it lowers
them slightly, from 92.0% to 91.6% in Croatia and from 88.2% to 87.4%
in Slovenia, and among the people with significant control of UK
companies it moves Croatian nationals from 97.5% to 97.3% and
Slovenian ones from 95.3% to 95.7%, a handful of records each way. The
dated figures are in
``docs/design/decisions/O6-two-family-names.md`` and
``docs/design/decisions/vocabulary-model.md``.


.. _spanish-portuguese-titles:

Spanish and Portuguese titles
-----------------------------

Turn on ``es`` when your data is Spanish names, ``es_ar`` when it is
Argentine ones, ``pt_br`` when it is Brazilian ones, ``pt_pt`` when it
is names from Portugal, and ``pt`` when it is Portuguese names from
anywhere else or from several countries. The default already reads the
titles described below, save two that ``es`` turns on; the larger
change is two family names, which the Spanish packs, ``pt_br`` and
``pt_pt`` read and ``pt`` leaves off.

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
:ref:`two-family-names`). It carries a list of about 1,000 Spanish given
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
    >>> spain.parse("García Márquez, Gabriel").surname2
    'Márquez'
    >>> spain.parse("María del Carmen García López").surname2
    'López'

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

A compound given name stays opt-in under the Spanish and Portuguese packs
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

Portuguese: two family names in Brazil and Portugal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Portuguese names write the mother's family name before the father's,
and Brazilian and Portuguese names often carry both. Turn on ``pt_br``
for Brazilian names and ``pt_pt`` for names from Portugal: each reads
two family names, guarded by a list of about 700 Portuguese given
names that the switch leaves where they stand:

.. doctest::

    >>> brazil = parser_for(locales.PT_BR)
    >>> portugal = parser_for(locales.PT_PT)
    >>> parse("Tiago Barros Queiroz").family
    'Queiroz'
    >>> brazil.parse("Tiago Barros Queiroz").family
    'Barros Queiroz'
    >>> portugal.parse("Ana Beatriz Costa").family
    'Costa'

The list is measured on ORCID's researchers in Portugal and Brazil,
from the words their holders type in the given-name box at least 70%
of the time. A word it lacks is taken all the same, which is the
switch's cost (``Ana Zélia Costa`` gives family ``Zélia Costa`` under
either pack).

``pt``, the pack chosen by language, leaves the switch off, the
reverse of Spanish, where the language pack carries it. ``pt`` serves
every Portuguese-speaking country, and the switch helps some and sinks
others: Angolan and Mozambican names lose under it, even with the
list, which holds few of the given names written there. Where reading
two family names helps your Portuguese data from another country,
turn it on beside ``pt``, or choose ``pt_pt``:

.. doctest::

    >>> from nameparser import Policy
    >>> parser_for(locales.PT).parse("Tiago Barros Queiroz").family
    'Queiroz'
    >>> pt_two = parser_for(locales.PT,
    ...                     base=Parser(policy=Policy(two_family_names=True)))
    >>> pt_two.parse("Tiago Barros Queiroz").family
    'Barros Queiroz'

A family of three surnames still keeps its first as a middle name
under both packs (``Leonardo Mirandela Gomes Paz`` gives middle
``Mirandela``, family ``Gomes Paz``): the switch takes one word.
Among ORCID's Brazilian researchers about one name in ten is written
that way.

Measured effect: Portuguese
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The figures are of ORCID's researchers, names agreeing in every box
with the filer, on records the list was not built from:

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Where the researcher works
     - Default and ``pt``
     - ``pt_br`` or ``pt_pt``
     - Records
   * - Portugal
     - 72.1%
     - 89.7%
     - 2,923
   * - Brazil
     - 50.3%
     - 79.8%
     - 2,850
   * - Cape Verde
     - 61.5%
     - 80.5%
     - 563
   * - São Tomé and Príncipe
     - 50.4%
     - 71.1%
     - 121
   * - Guinea-Bissau
     - 66.8%
     - 72.3%
     - 220
   * - Timor-Leste
     - 64.0%
     - 67.1%
     - 495
   * - Angola
     - 76.4%
     - 65.3%
     - 2,861
   * - Mozambique
     - 85.6%
     - 67.2%
     - 2,853

So Cape Verdean and São Toméan lists read better under ``pt_pt`` than
under ``pt``, and Angolan and Mozambican lists worse. ``pt_pt`` reads
Portugal's and Brazil's records 0.1 point below ``pt_br`` (89.6% and
79.7%): its own given names behind a particle (``da Conceição``), which
gain on Portugal's names as a whole, cost a few more of these records
than they fix.

Whether the switch helps also depends on who split the names. It
gains most on names their bearers split themselves, as ORCID's are.
It costs Brazilian inventors on US patents: their filers usually give
one surname as the family name and put the rest of the name in the
first-name box, and against that split, over all 15,029 Brazilian
records in the data, 75.7% read right by default or under ``pt`` and 60.2%
under ``pt_br``, while Portuguese inventors gain under ``pt_pt``
(57.6% → 66.1%). Most of the Brazilian names it breaks hold a second
surname among the given names (``Eder Ferreira`` / ``Rangel``, read
family ``Ferreira Rangel``). So choose ``pt_br`` or ``pt_pt``, by
country, for names whose family part is written whole, and keep ``pt`` for data
filed with a single surname as the family name.
Among the UK company register's filers the switch gains for
Portuguese (59.2% → 62.8%) and Brazilian (53.7% → 62.9%) nationals.

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
are from its entry on ``locales.ES_AR``, the Portuguese ones from its
entry on ``locales.PT_BR`` and ``locales.PT_PT``.


.. _romanized-indic-titles:

Romanized Indic titles
----------------------

The default reads the Devanagari and Bengali salutations as titles
(``श्रीमती``, ``শ্রীমতী``), since no Latin name is spelled in those
scripts, and leaves their romanizations to position, since a Latin
spelling can be a name. ``hi`` and ``bn`` turn on the romanized forms
whose leading use is the title, and ``hi`` one more, below:

.. doctest::

    >>> parse("Smt Nirmala Sitharaman").given
    'Smt'
    >>> hindi = parser_for(locales.HI).parse("Smt Nirmala Sitharaman")
    >>> hindi.title, hindi.given
    ('Smt', 'Nirmala')
    >>> parser_for(locales.BN).parse("Adhyapak Anisuzzaman Khan").title
    'Adhyapak'

``hi`` also reads ``Shri`` as the title, as an Indian parliament's
roll writes it. The cost falls on a person whose given name opens with
it (``Shri Kant``, ``Shri Lakshmi``), who reads the title there, so
``bn`` and the default leave it to position:

.. doctest::

    >>> parse("Shri Ravi Kumar Verma").given
    'Shri'
    >>> hindi = parser_for(locales.HI).parse("Shri Ravi Kumar Verma")
    >>> hindi.title, hindi.given
    ('Shri', 'Ravi')

``Sushri`` opens an Odia given name (``Sushri Sangita``) more often
than it is the title, so it stays a name word under the plain choice.
A strict Hindi choice, which reads no Odia names, reads it as the
title:

.. doctest::

    >>> parser_for(locales.HI).parse("Sushri Sangita Behera").given
    'Sushri'
    >>> parser_for(locales.HI, strict=True).parse("Sushri Sangita Behera").title
    'Sushri'

``Smt.`` and ``Shri.`` written with their period are titles at the head
of a name by default, packs or no; under ``hi`` they are titles ending
the name too. ``Pandit``, ``Sardar``, ``Kumari``,
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
own keeps its literal characters), as it does for Chinese, Japanese,
Korean, Lao, Burmese and Arabic-script ones,
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


.. _arabic-script-names:

Arabic-script names
-------------------

An Arabic, Persian or Urdu name written in Arabic script needs no pack
for its titles: the vocabulary reads them by default. The doctor, the
professor, the hajji and the sheikh are read written out
(``الدكتور``, ``الأستاذ``, ``الحاج``, ``الشيخ``); this section is about
the titles written short, and about initials.

Titles written short
~~~~~~~~~~~~~~~~~~~~

Arabic writes a title short with a full stop after a letter: ``د.``
(doctor), ``أ.`` (*ustādh*, professor or Mr.) and ``م.`` (lecturer or
engineer), and the academic ranks written short, as ORCID's records
from Iraq write them most,
``أ.د.`` (professor doctor), ``أ.م.د.`` (assistant professor
doctor), ``م.د.`` (lecturer doctor) and ``م.م.`` (assistant
lecturer). Each reads as the title with its full stop, without it,
glued to the name, or with its letters spaced:

.. doctest::

    >>> arabic_dr = parse("د. أحمد علي حسن")
    >>> arabic_dr.title, arabic_dr.given, arabic_dr.family
    ('د.', 'أحمد', 'حسن')
    >>> [parse(n).title for n in ("د أحمد علي", "أ.د.أحمد علي", "أ. م. د. أحمد علي")]
    ['د', 'أ.د.', 'أ. م. د.']

Ranks and offices are read in front of a name too: ``اللواء``
(major general), ``المستشار`` and ``المستشارة`` (counsellor, a
judge's title in Egypt) and ``السفيرة`` (ambassador):

.. doctest::

    >>> parse("اللواء أحمد علي").title
    'اللواء'

Egypt writes a title with a slash in place of its full stop (``د/``,
``أ.د/``, ``اللواء/``). Opening the name, or the given part after a
family comma, the slash reads as the full stop would, a separator in no field,
glued to the name or spaced from it; a Latin title written so reads
the same (``Dr/ Jane Smith``):

.. doctest::

    >>> arabic_slash = parse("د/ أحمد علي")
    >>> arabic_slash.title, arabic_slash.given
    ('د', 'أحمد')
    >>> [parse(n).title for n in ("د/أحمد علي", "د / أحمد علي", "Prof/Jane Smith")]
    ['د', 'د', 'Prof']

Initials
~~~~~~~~

In the name lists measured, Arabic script writes a letter with a full
stop before a name as a title and almost never for a name (Persian and
Urdu names were measured less). :meth:`~nameparser.ParsedName.initials`
gives nothing for a word in Arabic script, as for Han, Thai, Lao and
Burmese, and the name match reads a letter with a full stop as a word
of its own, not as an initial:

.. doctest::

    >>> parse("أحمد علي حسن").initials()
    ''

Where the reading stops
~~~~~~~~~~~~~~~~~~~~~~~

- **A title behind another title** that is not listed stays a name
  word: ``الأستاذ المساعد`` (assistant professor) reads ``المساعد`` as
  the given name.
- **A vowel mark on the letter** (``دُ.``) or a presentation form
  (``ﺩ.``) is not read as the title.
- **A Western name written in Arabic script with an initial** has no
  initials, and ``و.`` (W.) is read as ``و``, "and", which joins the
  name: ``جورج و. بوش`` reads as one given name.



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

.. _french-dit-names:

French ``dit`` names
--------------------

``dit`` and its feminine ``dite`` ("called") join two words of a name
in two uses: a hereditary French family name of two parts, one legal
surname in France, Quebec and Switzerland (``Dupont dit Lebrun``), and
a West African alias written beside the given name (``Mamadou dit
Madou``). Choosing French reads either as one part of the name; the
default does not, and reads the first half as a middle name:

.. doctest::

    >>> french_names = parser_for(Locale(code="fr", lexicon=Lexicon.empty(),
    ...                                  languages=frozenset({"fr"})))
    >>> parse("Jean Dupont dit Lebrun").family
    'Lebrun'
    >>> french_names.parse("Jean Dupont dit Lebrun").family
    'Dupont dit Lebrun'
    >>> french_names.parse("Mamadou dit Madou Traore").given
    'Mamadou dit Madou'

It is a choice rather than the default because ``Dit`` and ``Dite`` are
also given names and surnames (a Cantonese and a Latvian given name, and
a surname ``Dite``, among them), and the choice reads the word as a
connective wherever it stands:

- **A name of three words** with the name in the middle is read as one
  given name, as ``Juan and Garcia`` is (``Sok Dit Chan`` gives given
  ``Sok Dit Chan`` and no family name).
- **Opening a name of three words or more**, it joins the next word to
  the given name (``Dit Jean Dupont`` gives given ``Dit Jean``).
- **Ending a name**, it joins the word before it to the family name
  (``Tran Thi Dit`` gives family ``Thi Dit``).
- **Before a comma and a suffix**, the joined name is read as the given
  name and the family is left empty (``Dupont dit Lebrun, Jr.``).
- **Case repair** of a name written in one case writes it in lower
  case (``SOK DIT CHAN`` gives ``Sok dit Chan``), and ``initials()``
  gives it no initial inside a joined part (``Sok Dit Chan`` gives
  ``S. C.``), alone in its field it keeps one (``Jean Dit`` gives
  ``J. D.``).

Written with hyphens (``Dupont-dit-Lebrun``) the name is one word and
its fields read the same either way; case repair writes its ``dit`` in
lower case under the choice (``JEAN DUPONT-DIT-LEBRUN`` gives ``Jean
Dupont-dit-Lebrun``).

The connective joins one word on each side, so a surname whose second
half opens with a particle, in any language, is split unless a family
comma follows it (a suffix comma does not keep it): written given name
first, the particle goes to the middle
name with the first half (``Jean Dupont dit de Lebrun`` gives family
``Lebrun``, ``Karim Haddad dit Abou Nasr`` family ``Nasr``; of a run
such as ``de la`` only the first word), and under a family-first order
the second half leaves the family instead (``Dupont dit de Lebrun
Jean`` gives family ``Dupont dit de``). After a family comma the
surname is read whole (``Dupont dit de Lebrun, Jean``).

.. _burmese-names:

Burmese names
-------------

Turn on ``locales.MY`` when your data is Burmese names written in Latin
letters, and choose it strictly when your list holds nothing else (below).
``my`` is the language tag of Burmese; Malaysia, whose region code is
also MY, writes Malay, ``ms``, which this pack is not for.

A Burmese name has no family name: every word is a personal name, and
an honorific goes in front, ``U`` for a man and ``Daw`` for a woman.
The parser reads by position, so under the pack the last word is the
family name, as in any name, and the honorific is the title:

.. doctest::

    >>> parse("U Thein Sein").given
    'U'
    >>> burmese = parser_for(locales.MY)
    >>> thein_sein = burmese.parse("U Thein Sein")
    >>> thein_sein.title, thein_sein.given, thein_sein.family
    ('U', 'Thein', 'Sein')

A list of nothing but Burmese names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Choose the pack strictly, ``parser_for(locales.MY, strict=True)``
(:ref:`strict-choice`). Many Burmese syllables are spelled like
another language's word: ``San``, ``La`` and the Chin ``Van`` like
Spanish, Italian or Dutch particles, which take every word after them
into the family name, and ``Pe``, ``Lat``, ``Ei``, ``Si``, ``Pa`` and
``Ra`` like English credentials, which end a name written in capitals.
A strict choice reads no other language's words, so each is a name
word:

.. doctest::

    >>> strict_burmese = parser_for(locales.MY, strict=True)
    >>> burmese.parse("Daw Aung San Suu Kyi").family
    'San Suu Kyi'
    >>> suu_kyi = strict_burmese.parse("Daw Aung San Suu Kyi")
    >>> suu_kyi.title, suu_kyi.middle, suu_kyi.family
    ('Daw', 'San Suu', 'Kyi')
    >>> burmese.parse("THEIN AUNG PE").suffix
    'PE'
    >>> strict_burmese.parse("THEIN AUNG PE").family
    'PE'

The English military ranks such lists write, and ``Sir``, are the
Burmese vocabulary's own, so a strict choice keeps them, written whole
or short (``Senior General``, ``Lt Gen``, ``Maj Gen``, ``Brig Gen``,
``Col``, ``Capt``, ``Rear Admiral``, ``Cdr``). ``Mg``, Maung written
short, is the given name, where by default and under the plain pack
it is read as the military abbreviation:

.. doctest::

    >>> strict_burmese.parse("Lt Gen Kyaw Win").title
    'Lt Gen'
    >>> burmese.parse("Mg Htoo Aung").title
    'Mg'
    >>> strict_burmese.parse("Mg Htoo Aung").given
    'Mg'

On 2,990 names of people from Myanmar, from sanctions and politically
exposed persons lists and from Wikidata, read right is the honorific
as the title and the last word as the family
(``docs/design/decisions/vocabulary-collisions.md``, :issue:`1231`,
:issue:`1483`):

.. list-table::
   :header-rows: 1

   * - Parser
     - As written
     - In capitals
   * - ``Parser()``
     - 94.8%
     - 94.5%
   * - ``parser_for(locales.MY)``
     - 98.1%
     - 97.8%
   * - ``parser_for(locales.MY, strict=True)``
     - 2,989 of 2,990
     - 2,989 of 2,990

What a strict choice costs other names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A strict choice drops every word only another language reads, from
every name, so keep it to a list that is wholly Burmese:

- **Particles, credentials and titles of other languages** are name
  words. ``Jan van Dijk`` gives middle ``van``, and a credential after
  a comma can become the given name (``Jane Doe, PA`` gives given
  ``PA``, family ``Jane Doe``). The words every language
  shares are kept, ``Dr``, ``PhD``, ``MD`` and ``MSc`` among them.
- **A rank that is also a given name** is the rank: ``Gen``, ``Maj``,
  ``Brig`` and ``Major`` opening a name are titles (``Gen Goto`` gives
  title ``Gen``), where by default they are the given name unless a
  title phrase follows.

.. doctest::

    >>> strict_burmese.parse("Jan van Dijk").family
    'Dijk'
    >>> strict_burmese.parse("Jane Doe, PA").given
    'PA'
    >>> burmese.parse("Jane Doe, PA").suffix
    'PA'

On some 660,000 distinct names that are mostly not Burmese, the strict
choice reads about one in eleven differently from the plain pack in
their fields (:issue:`1483`; the measurement is in the source
repository's ``docs/design/decisions/vocabulary-collisions.md``).

What the pack leaves as it is
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Other honorifics and prefixes.** ``Ko``, ``Ma`` and ``Maung`` are
  honorifics too but also name syllables (``Maung Maung Kyaw``), and the
  ethnic prefixes ``Saw``, ``Sai``, ``Nang``, ``Naw``, ``Khun`` and
  ``Mahn`` are part of the name, so each stays a name word.
- **An honorific and one word.** ``U Thant`` gives title ``U``, family
  ``Thant``, as a title and one name word reads in any name.
- **Military and religious styles** (``Bogyoke``, ``Sayadaw``) are read
  as name words, as by default (``Ledi Sayadaw`` gives family
  ``Sayadaw``).
- **Burmese script.** The pack reads Latin letters only; ``ဦး`` and
  ``ဒေါ်`` have no reading yet.

When not to use it
~~~~~~~~~~~~~~~~~~

The plain pack reads names that are not Burmese as the default does,
save two words, ``U`` and ``Daw``, read as titles wherever a title is
read (``Daw Smith`` gives title ``Daw``), and ``U`` as a letter of a
word joined by full stops (``J.U. Smith`` gives title ``J.U.``). ``U``
is the honorific however it is
written, so an initial ``U.`` can be read as the title. ``Smith, U.`` and ``Dr. U.
Smith`` give no given name, though ``John U. Smith`` and ``Smith, John
U.`` keep it an initial:

.. doctest::

    >>> grant = burmese.parse("U. S. Grant")
    >>> grant.title, grant.given
    ('U.', 'S.')

A Korean name written with no comma and opening with the surname ``U``
reads ``U`` as the title under the pack (``U Minjun``), where ``U,
Minjun`` keeps it as the family name. Chosen strictly, the pack reads
a run of initials opening with ``U`` as the title too, which the plain
pack leaves initials (``U.S. Grant`` gives title ``U.S.``, family
``Grant``). Keep the pack to a parser of
its own for the Burmese names in your data.

.. _malay-names:

Malay names
-----------

Turn on ``locales.MS`` when your data is Malaysian names, Malay ones
written with the titles Malaysian lists put in front of them. ``ms`` is
the language tag of Malay (Burmese is ``my``, :ref:`burmese-names`).

A Malay name has no family name either: a given name, then ``bin``
(son of) or ``binti`` (daughter of) and the father's name, which the
default reads as the family already. What the pack adds is the words
written before the name. ``Encik`` (Mr.) is a title by default; the
pack reads ``Puan`` (Mrs.), ``Cik`` (Miss), ``Ustaz`` and ``Ustazah``
(a religious teacher) and ``Cikgu`` (teacher) as titles too:

.. doctest::

    >>> parse("Puan Siti binti Ahmad").given
    'Puan'
    >>> malay = parser_for(locales.MS)
    >>> siti = malay.parse("Puan Siti binti Ahmad")
    >>> siti.title, siti.given, siti.family
    ('Puan', 'Siti', 'binti Ahmad')
    >>> hafiz = malay.parse("USTAZ HAFIZ BIN OMAR")
    >>> hafiz.title, hafiz.given, hafiz.family
    ('USTAZ', 'HAFIZ', 'BIN OMAR')

Each is off by default, because a name elsewhere is written with it or
because only Malaysian lists write it: ``Puan`` is an Indonesian given
name, so the default keeps ``Puan Maharani``'s given name, and the pack
does not. Choose the pack
for Malaysian lists, not Indonesian ones.

The honours ``Datuk``, ``Dato'`` and ``Datin`` and the pilgrim's
``Hajah`` are titles by default, each addressing the given name, as
``Sir`` does. The pack adds the honours that are names elsewhere: ``Tun``, a
Chinese and Burmese name; ``Haji``, a given name and a surname;
``Dato`` written without its apostrophe, an Italian surname and a
Georgian given name; and the phrases ``Tan Sri`` and ``Puan Sri``:

.. doctest::

    >>> ahmad = parse("Datuk Ahmad bin Ali")
    >>> ahmad.title, ahmad.given, ahmad.family
    ('Datuk', 'Ahmad', 'bin Ali')
    >>> parse("Tan Sri Muhyiddin Yassin").given
    'Tan'
    >>> yassin = malay.parse("Tan Sri Muhyiddin Yassin")
    >>> yassin.title, yassin.given, yassin.family
    ('Tan Sri', 'Muhyiddin', 'Yassin')
    >>> malay.parse("Haji Abdul Hadi Awang").title
    'Haji'

``Tan``, the commonest Chinese surname in Malaysia, and ``Sri``, a given
name, are titles only in their phrases: alone each stays the given
name, and the pack reports the title it might be, so a Chinese name
written family first reports one under the pack (``Tan Chee Chai``
gives given ``Tan`` and a ``title-or-name`` report). A ``Sri`` that is a
given name behind the surname ``Tan`` reads as the phrase
(``Tan Sri Wahyuni`` gives title ``Tan Sri``), and so does either word
behind a style (``Hon. Tan Ah Kow`` gives title ``Hon. Tan``).

On Malaysia's election candidates, some 3,000 names written in
capitals, the default reads an honour (``DATO'``, ``DATUK``) as the title
in about 170 of them; the word behind it is then the given name, which
for a qualifier of the honour (``DATO' SRI``, ``DATUK SERI``) or a title
the default does not read (``HAJI``, ``CIKGU``) is still not the
person's. The pack reads about 250 differently from the default:

- **About 200 read a title the default read as the given name**, most
  of them ``USTAZ``, ``CIKGU``, ``HAJI`` and ``DATO``. ``Cikgu`` written
  in two words (``CIK GU``) reads given ``GU``.
- **The rest read the same and add a report**, most of them Chinese
  names written family first with ``TAN``.

Among the records ORCID, PatentsView and Companies House hold of
Malaysians, Indonesians and Singaporeans, each split into boxes by the
person or the filer, the share whose boxes the parse matches moves by
at most a tenth of a point under the pack (:issue:`1179`,
:issue:`1180`).

What the pack leaves as it is
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Tuan`` (Mr., Sir) stays a name word. Malaysians who file their own
names write it first as a hereditary prefix, repeated before the
father's name, and a Vietnamese given name is written so too:

.. doctest::

    >>> aminah = malay.parse("Tuan Aminah binti Tuan Yusof")
    >>> aminah.title, aminah.given, aminah.family
    ('', 'Tuan', 'binti Tuan Yusof')

``Sri`` and ``Seri`` written behind a head honour, as its qualifier,
stay name words (``Datuk Seri Anwar Ibrahim`` gives title ``Datuk``,
given ``Seri``), and so do ``YB``, ``YM`` and ``YA`` and the police
ranks (:issue:`1180`). ``Haji`` inside the father's name is a name word
(``Ahmad bin Haji Abdullah`` gives family ``bin Haji Abdullah``).
``bt``, written short for ``binti``, can still be read as a credential
(Baronet), as by default (``Nur Aina bt Rosli``); :ref:`malay-bt`
shows how to remove it.

Plain, not strict
~~~~~~~~~~~~~~~~~

Choose the pack plainly. Malaysian lists mix Malay, Chinese and Indian
names with English and Arabic titles, and a strict choice of ``ms``
reads only the words of ``ms`` and those shared by every language, so
it drops ``Abdul``'s join and English titles such as ``Sir``: on
ORCID's Malaysian holders it matches about half a point fewer names'
boxes than the plain choice (the measurement is in the source
repository's ``docs/design/decisions/salutation-titles.md``).

