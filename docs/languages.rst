Notes by language
=================

What the shipped packs do for Czech, Slovak, Slovenian and Croatian names, Spanish and Portuguese titles, romanized Indic titles, Vietnamese and Mongolian names, and Maghrebi, Amazigh and Hebrew particles.


.. _west-south-slavic-packs:

Czech, Slovak, Slovenian and Croatian names
-------------------------------------------

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

    >>> from nameparser import Lexicon, Locale, Parser, locales, parse, parser_for
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

.. _spanish-portuguese-titles:

Spanish and Portuguese titles
-----------------------------

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


.. _maghrebi-hebrew-particles:

Maghrebi, Amazigh and Hebrew particles
--------------------------------------

Family names in Morocco, Algeria, Tunisia and Mauritania, written in
French spelling, often open with a word that joins the next one: the
Amazigh ``Ait`` and ``Nait`` ("the people of"), the Hassaniya ``Ould``
("son of"), ``Ouled`` ("children of", in Algerian and Moroccan family
names), and ``El``, the article ``al`` as
Morocco, Algeria and Egypt spell it. The default reads each as part of the
family name, and ``Ould``, with which a Mauritanian name still forms the
father's name, fills ``patronymic`` too. ``El``, like ``Al``, is also a
given name where it opens one (``El Mehdi``), so there it stays the
given name and reports the fork:

.. doctest::

    >>> parse("Youssef Ait Haddou").family
    'Ait Haddou'
    >>> parse("Sara El Haddou").family
    'El Haddou'
    >>> haddou = parse("Ahmed Ould Haddou")
    >>> haddou.family, haddou.patronymic
    ('Ould Haddou', 'Ould Haddou')

``Ben`` ("son of") opens Tunisian and Israeli family names the same way
(``Ben Haddad``), but it is also the given name Ben, and a British
middle name, standing where the particle would claim it, so the default
leaves it to position. The Arabic and Hebrew packs, ``locales.AR`` and
``locales.HE``, each choose their one language and read it as the
family name; a ``Ben`` opening a name stays the given name and reports
the fork, save under a strict Arabic choice (``strict=True``), which
drops English's given name Ben and reads a leading ``Ben`` as the family
name:

.. doctest::

    >>> parse("Karim Ben Haddad").family
    'Haddad'
    >>> arabic = parser_for(locales.AR)
    >>> arabic.parse("Karim Ben Haddad").family
    'Ben Haddad'
    >>> arabic.parse("Ben Haddad").given
    'Ben'

Among ORCID's researchers, who split their own names into a given and a
family box, the names agreeing in both boxes rise from 87.6% by default
to 96.1% under either pack in Tunisia, and from 92.7% to 93.5% in
Israel (measured 2026-11-12; decisions/vocabulary-collisions gives the
command). A listing written family name first without a
comma reads whole as the family name (``Ait Haddou Karim``), as one
opening with ``de`` does; write the comma or declare the order. And a
compound given name written with ``El`` inside it, as Algerian names
are, gives the article and the rest to the family name (``Nour El Houda
Haddou`` gives family ``El Houda Haddou``): among ORCID's Algerian
researchers ``El`` read this way breaks 135 names for 37 it fixes,
where it fixes 2,001 for 26 in Morocco, 286 for 20 in Egypt and 432 for
6 in Lebanon (measured 2026-11-12).

The packs are for family names written with ``Ben``, not for a civil
register's chain of fathers' names: ``Karim ben Ali ben Salah Haddad``
gives middle ``ben Ali``, family ``ben Salah Haddad`` under either pack,
where the default keeps the chain in the middle name and reads the
family right (a Tunisian register-style list read 140 of its 158 names
right by default and 24 with ``ben`` read, :issue:`1248`).

Choosing Arabic also costs English's reading of ``abd``, which Arabic
reads as a given name (``Abd Rahman``), so the credential ABD (All But
Dissertation) is a name word under ``locales.AR``: ``Jane Smith, ABD``
gives given ``ABD``, family ``Jane Smith``. Choose ``en`` too to keep it:

.. doctest::

    >>> english = Locale(code="en", lexicon=Lexicon.empty(),
    ...                  languages=frozenset({"en"}))
    >>> parser_for(locales.AR, english).parse("Jane Smith, ABD").suffix
    'ABD'

A strict Arabic choice also drops the Amazigh ``Ait`` and ``Nait``, which
are ``ber``'s (Berber), so for Moroccan and Algerian data choose ``ber``
too: ``parser_for(locales.AR, Locale(code="ber", lexicon=Lexicon.empty(),
languages=frozenset({"ber"})), strict=True)``.

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
