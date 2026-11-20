Behavior: Policy
=================

When your data source or application needs different parsing behavior
— a different name order, stricter suffix rules, extra delimiters —
set it on :class:`~nameparser.Policy`, a small, closed set of fields.
`Setting a field`_ shows the call, and `The fields`_ lists every field
with its default and, where there is one, the section that covers it.

Setting a field
---------------

Build a ``Policy`` with the fields you want changed and hand it to a
:class:`~nameparser.Parser`. Every field you leave out keeps its
default, and ``parse()`` itself always reads under the defaults:

.. doctest::

    >>> from nameparser import Parser, Policy, parse
    >>> parse("Tomas Vilar Quintero").family           # the default
    'Quintero'
    >>> folded = Parser(policy=Policy(middle_as_family=True))
    >>> folded.parse("Tomas Vilar Quintero").family
    'Vilar Quintero'

A ``Policy`` is frozen, so to change one field of a policy you already
have, a parser's or a pack's, copy it with ``dataclasses.replace``:

.. doctest::

    >>> import dataclasses
    >>> dataclasses.replace(folded.policy, two_given_names=True)
    Policy(middle_as_family=True, two_given_names=True)

A locale pack carries its settings as a
:class:`PolicyPatch <nameparser.PolicyPatch>`, the fields it changes
and nothing else. To apply one directly -- without going through a
locale pack -- call :meth:`Policy.patched()
<nameparser.Policy.patched>`:

.. doctest::

    >>> from nameparser import PolicyPatch
    >>> Policy().patched(PolicyPatch(middle_as_family=True))
    Policy(middle_as_family=True)

The fields
----------

Order and name structure
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 24 12 42

   * - Field
     - Type
     - Default
     - Effect
   * - ``name_order``
     - an order constant
     - ``GIVEN_FIRST``
     - Assigns positional input to given/middle/family in this order:
       ``GIVEN_FIRST``, ``FAMILY_FIRST`` or
       ``FAMILY_FIRST_GIVEN_LAST``. A family comma overrides it. See
       :ref:`name-order`.
   * - ``script_orders``
     - pairs of ``Script`` and an order
     - family-first scripts
     - Assigns a name in one of these scripts in the paired order,
       whatever ``name_order`` says. The default,
       :data:`~nameparser.DEFAULT_SCRIPT_ORDERS`, is family-first for a
       name wholly in Han or Hangul, or in kanji and kana other than
       katakana alone. See :ref:`east-asian-defaults`.
   * - ``segment_scripts``
     - ``frozenset[Script]``
     - Hangul
     - Scripts whose unspaced names are split into surname and given
       name. See :ref:`east-asian-defaults`.
   * - ``patronymic_rules``
     - ``frozenset[PatronymicRule]``
     - empty
     - Reorders patronymic-shaped names via opt-in detectors — East
       Slavic formal order (``EAST_SLAVIC``) or Turkic reversed order
       (``TURKIC``) — but stands down under a declared
       ``FAMILY_FIRST`` or ``FAMILY_FIRST_GIVEN_LAST`` ``name_order``.
       Each rule also fills ``ParsedName.patronymic``. The ``ru`` and
       ``tr_az`` rows of :ref:`shipped-packs` describe what each rule
       detects.
   * - ``middle_as_family``
     - ``bool``
     - ``False``
     - Folds ``middle`` into ``family`` instead of splitting them —
       for naming systems with no middle-name concept.
   * - ``two_family_names``
     - ``bool``
     - ``False``
     - Reads the last two name words as the family name (the first
       two under a family-first order), for data where people carry
       two family names (Spain, most of Latin America). See
       :ref:`two-family-names`.
   * - ``two_given_names``
     - ``bool``
     - ``False``
     - Reads the middle name beside the given name as part of it, for
       data where people carry a compound given name and no middle
       name (``María José``). See :ref:`two-given-names`.
   * - ``lone_name_word``
     - ``Role.GIVEN`` or ``Role.FAMILY``
     - ``Role.GIVEN``
     - The field a name of one word reads as, under every
       ``name_order``. See :ref:`lone-name-word`.
   * - ``initials_as_family``
     - ``bool``
     - ``False``
     - Reads two or more single letters ending a name as its family
       name (``Lakshmi R S``), for South Asian data where the letters
       stand for a family name. See :ref:`initials-as-family`.
   * - ``capitals_as_family``
     - ``bool``
     - ``False``
     - Reads the words a name writes in capitals as its family name
       (``DUPONT Jean``), for data whose source writes every family
       name in capitals. See :ref:`capitals-as-family`.

Brackets and suffixes
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 24 12 42

   * - Field
     - Type
     - Default
     - Effect
   * - ``nickname_delimiters``
     - ``frozenset[tuple[str, str]]``
     - the shipped pairs
     - Routes content enclosed by these delimiter pairs to
       ``nickname``. The default,
       :data:`~nameparser.DEFAULT_NICKNAME_DELIMITERS`, is straight
       quotes and parentheses plus the typographic conventions (smart
       quotes, guillemets, CJK brackets, ...). See :ref:`brackets`.
   * - ``maiden_delimiters``
     - ``frozenset[tuple[str, str]]``
     - empty
     - Routes content enclosed by these delimiter pairs to ``maiden``
       instead of ``nickname``. Needed only for a clause that does not
       announce itself: ``"(née Jones)"`` is a maiden name without it.
       See :ref:`brackets`.
   * - ``extra_suffix_delimiters``
     - ``frozenset[str]``
     - empty
     - Adds separators that split suffix groups, e.g. ``" | "`` for
       ``"Jane Smith, RN | CRNA"``. Additions only — the comma, the
       semicolon, and a hyphen or slash standing alone split suffix
       groups after a whole name and cannot be replaced. See
       :ref:`suffix-delimiters`.
   * - ``lenient_comma_suffixes``
     - ``bool``
     - ``True``
     - Reads an initial-shaped suffix word after a comma as a suffix:
       ``"John Smith, V"`` is John Smith the fifth. ``False`` reads
       ``V`` as a given-name initial instead. See
       :ref:`lenient-comma-suffixes`.
   * - ``unlisted_dotted_suffixes``
     - ``bool``
     - ``True``
     - Reads an unlisted dotted acronym such as ``X.Y.Z.`` as a
       credential where the name's shape allows it. See
       :ref:`unlisted-credentials`.
   * - ``unlisted_caps_suffixes``
     - :class:`~nameparser.CapsSuffixes`
     - ``AFTER_COMMA``
     - Where an unlisted all-caps word such as ``XYZ`` reads as a
       credential: after a comma (``AFTER_COMMA``), at the end of a
       name as well (``EVERYWHERE``), or nowhere (``OFF``). See
       :ref:`unlisted-credentials`.

Characters
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 24 12 42

   * - Field
     - Type
     - Default
     - Effect
   * - ``strip_emoji``
     - ``bool``
     - ``True``
     - Excludes emoji from tokenization — they appear in no field or
       rendered view, though ``original`` keeps them. See
       :ref:`strip-flags`.
   * - ``strip_bidi``
     - ``bool``
     - ``True``
     - Excludes bidirectional control characters the same way. See
       :ref:`strip-flags`.

.. _name-order:

Family-first name order
------------------------

Set ``name_order`` when your records write the family name first
without a comma (see `The order belongs to the source, not the
language`_). It is the field most likely to matter for data that is
not in Western order.

Positional input is assigned in the order you declare — with the four
vocabulary exceptions noted under :ref:`order-vocabulary-first` — so a
name written family-first — Hungarian, here — parses as written
instead of needing to be rearranged afterwards:

.. doctest::

    >>> from nameparser import Parser, Policy, FAMILY_FIRST, parse
    >>> parse("Nagy Laszlo Peter").family            # default GIVEN_FIRST
    'Peter'
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> name = family_first.parse("Nagy Laszlo Peter")
    >>> name.family, name.given, name.middle
    ('Nagy', 'Laszlo', 'Peter')

Vietnamese order: given name last
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
do (:ref:`east-asian-defaults`) — Vietnamese is written in the Latin
alphabet, which carries no order of its own — so it applies only where
you set it.

For Vietnamese data, the ``vi`` pack (``parser_for(locales.VI)``) sets
this order and also keeps the Vietnamese syllables other languages read
as particles or connectives (``Van``, ``Le``, ``Do``, ``The`` and
others) as name words, and ``Chi``, ``Ba`` and ``Do`` out of the
credentials (see :ref:`vietnamese-names`); the bare ``Policy`` above is
for data that wants the order alone.

The order belongs to the source, not the language
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Malaysia's election lists are another such source: they write a
Chinese name family first (``TAN KOK LEONG``), nearly every three-word
Chinese name on them (the count is in
``docs/design/decisions/O4-positional-assignment-and-declared-order.md``).
Such a name often writes its given name as two words, which a
family-first order reads as a given name and a middle name;
:ref:`two-given-names-chinese` shows the setting that keeps them
together.

.. _mixed-name-order:

A list that mixes orders
~~~~~~~~~~~~~~~~~~~~~~~~

A source can also mix orders, name by name. Singapore's Parliament
list writes some members with a Chinese surname given first (in the
shape of ``Grace Lim``) and others family first (``Tan Kok Leong``),
and nothing in a Chinese name's spelling tells which: of its 77 such members, 27
are written given first and 33 family first, and most of the rest
carry an English name as well (:issue:`1183` has the counts).
Malaysia's lists mix orders too: a candidate known by an English
given name is written given first (``GRACE TAN``), the Chinese names
family first.

No one setting reads such a list. The default order reads the names written given
first, and ``FAMILY_FIRST`` with ``two_given_names`` the names written
family first, so each setting misreads the other group.

The order then has to come from outside the name: a separate field in
the source, or capitals where the source writes the family name in
them (:ref:`capitals-as-family`), which helps only where the list writes
the rest of the name in mixed case. ``Parser.suggest`` cannot supply
it: it suggests no order where neither order holds the share it needs
(:ref:`suggest-deciding`), as for Malaysia's Chinese candidates, and
where the names written one way carry more of the evidence, it
suggests that order for the whole list. Either way the names written
the other way stay misread.

A comma still wins
~~~~~~~~~~~~~~~~~~

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

.. _order-vocabulary-first:

Where the vocabulary answers first
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In four places the reading comes from the vocabulary rather than from
the position the order assigns:

- **A middle word that is also a shipped particle** is claimed by the
  vocabulary. That is why the Vietnamese example above is not the more
  obvious ``"Nguyen Van Minh"``: ``Van`` is the Dutch particle ``van``,
  so that name reads family ``Nguyen`` with ``Van Minh`` given under
  *both* family-first orders, and the choice between them makes no
  difference. The ``vi`` pack takes the particle reading out, so under
  it the name reads middle ``Van``, given ``Minh``.
- **A never-given particle opening the name** overrides the declared
  order outright: where a particle that can never be a given name
  stands alone as the opening piece, the surname starts there in every
  ``name_order`` (`Where a leading particle run stops`_ shows how far
  it reaches). ``"de Mesnil"`` is family ``de Mesnil`` under
  both family-first orders exactly as it is by default, not family
  ``de`` with ``Mesnil`` given — a word that can never be a given name
  leaves the order nothing to decide.
- **A particle that can be a given name, written in lower case beside
  capitals,** opens the surname too, but only under a family-first
  order (since 3.0): ``"van Gogh"`` reads family ``van Gogh`` there,
  while ``"Van Gogh"`` reads family ``Van``, given ``Gogh``, its
  capital leaving a real question to answer. Under the default order
  the particle is the given name in both spellings.
- **A lone name word beside a given-name title** is the given name in
  every ``name_order`` (since 2.5): ``"Sir John"`` reads given ``John``
  under both family-first orders, as it does by default, while
  ``"Dr John"`` still reads family ``John`` there.

:ref:`Words that are also ordinary names <ambiguous-words>` covers
dropping a word from a vocabulary, or moving a particle between the
never-given ones and those that can be a given name.

Where a leading particle run stops
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Declaring an order also bounds how far a *leading* particle run
reaches. With no order declared, nothing marks where the surname ends
and a particle followed by several words really can be all surname, so
the whole name is read as one. Declaring family-first asserts that what
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

Declaring the order settles where a surname ends
------------------------------------------------

If your records are family-first without commas,
``Policy(name_order=FAMILY_FIRST)`` reads them the way the comma format
is already read, a particle that ends the name included, except where
that particle is also a suffix (see `Where the correspondence
stops`_).

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

That pair is not a coincidence but one shape written two ways: the
family-first form is the comma form with the comma removed and the
family folded inline — titles included, so a title that the comma form
writes after the comma leads the name instead. The family-first forms
are listed in :doc:`shapes`, and the measurement over every particle
shipped when the rule landed is in
``docs/design/decisions/P6-trailing-orphan-particle.md``
(:issue:`467`).

Where the correspondence stops
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Three limits keep that statement honest:

- **It covers one shape, not comma deletion in general.** A name whose
  shape changes when the comma is removed — a title or suffix crossing
  to a different position — parses as the shape it becomes, not as a
  disagreeing reading of the comma form.
- **A word that is both particle and suffix reads differently in the two
  writings.** The shipped words in both vocabularies are ``do``,
  ``mc`` and ``vd``. The
  particle attachment outranks the suffix reading on the comma side
  alone — that is the scope the rule is stated in — so
  ``parse("Ménil, Christophe vd")`` reads family ``vd Ménil``, while
  ``family_first.parse("Ménil Christophe vd")`` reads family ``Ménil``
  and suffix ``vd``. It is that asymmetry, not a precedence, that
  breaks the correspondence, and a listing ending in one of those words
  is the only kind the two writings read differently among the shipped
  particles, not scatter.
- **Only** ``FAMILY_FIRST`` **is reached.** It is the only order that
  puts a trailing piece in the *middle*, where a particle means nothing.
  ``FAMILY_FIRST_GIVEN_LAST`` puts it in the given slot, where your own
  declaration already says it is the given name, and no comma format
  writes the given name last, so that order has no comma twin to
  correspond to in the first place:

.. doctest::

    >>> given_last.parse("Nguyen Thi Van").given
    'Van'

.. _lone-name-word:

Names written as one word
-------------------------

Set ``lone_name_word`` to ``Role.FAMILY`` when the one-word names in
your data are surnames. Which field a word written alone fills depends
on where the data came from rather than on the order its longer names
are written in: a list of the names people go by holds given names, a
column of surnames holds family names.

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

With the switch set:

.. doctest::

    >>> surnames = Parser(policy=Policy(lone_name_word=Role.FAMILY))
    >>> surnames.parse("Nguyen").family
    'Nguyen'
    >>> surnames.parse("John Smith").family          # longer names unchanged
    'Smith'

Anything that does decide the word still decides it first, whatever the
switch says:

- **A title**: ``"Mr. Johnson"`` is family ``Johnson``, ``"Sir John"``
  given ``John``.
- **A nickname or maiden name beside it**: ``"Anh (Annie)"`` is
  family ``Anh``.
- **A family comma**: ``"Anh, Jr."`` is family ``Anh``, ``", Anh"``
  given ``Anh``.
- **A name its script reads family-first**: Han, Hangul, or kana other
  than katakana alone (``"みなみ"`` is family ``みなみ``).

Through 2.x the field followed ``name_order``, so a family-first order
read a lone word as the family name.

.. _two-family-names:

Names with two family names
---------------------------

Turn on ``two_family_names`` when the people in your data carry two
family names and write both together, after the given names (or first,
under a family-first order), and only then:
:ref:`What it costs <two-family-names-cost>` shows what it does to
other names. ``locales.ES``, ``locales.ES_AR``, ``locales.PT_BR`` and
``locales.PT_PT`` turn it on together with a list of given names that it holds back (see
`Keeping a given name out of the family`_).

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

``two_family_names=True`` reads the last two name words as the family,
or the *first* two under a family-first ``name_order``. Given names
before them stay given and middle names, a particle counts with the
word it attaches to, titles and suffixes are not counted, and an
initial written alone never joins the family:

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

The family is divided by its own words however it was read: before a
family comma, and where it opens with a particle, the particles going
with the word they attach to. A family of three name words is left
whole:

.. doctest::

    >>> two_names.parse("García López, Ana").surname2
    'López'
    >>> ruiz = two_names.parse("Juan de la Vega Ruiz")
    >>> ruiz.surname1, ruiz.surname2
    ('de la Vega', 'Ruiz')
    >>> two_names.parse("Juan de la Vega Ruiz Soto").surname2
    ''

What it leaves alone
~~~~~~~~~~~~~~~~~~~~

- **A family that already holds two names** keeps what it has, whether
  a hyphen or ``y`` joins them (``"Ana María García-López"``, ``"José
  Ortega y Gasset"``) or a particle chain took them both (``"Ana María
  de la Vega Rodríguez"`` reads family ``de la Vega Rodríguez``); the
  particle chain's family is still divided by its own words (``surname2``
  ``Rodríguez``), where the hyphen's and ``y``'s stay one unit.
- **A name of two words** is unchanged.
- **A comma naming the family** decides by itself, so ``"García López,
  Ana"`` needs no switch for its ``family``; the switch divides it into
  ``surname1`` and ``surname2``.
- **Kaur and Singh** stay where they stand (see :ref:`kaur-singh`).

.. _two-family-names-cost:

What it costs
~~~~~~~~~~~~~

Turn it on only for data written this way:

- **One family name behind two given names.** ``"Juan Carlos Pérez"``
  loses ``Carlos`` to the family under the switch, and Argentine names,
  which carry one family name, are mostly that shape.
- **Portuguese and Brazilian names.** They carry two family names too,
  the mother's first, but the people who write them often give the last
  one alone as their family name. Among the UK company register's
  Portuguese filers the switch breaks about six names for every five it
  mends, while among ORCID's researchers working or living in Portugal,
  who split their own names into its boxes, it mends about twice what
  it breaks: the two populations disagree, so measure the data you have
  before switching it on.
- **Filipino names.** They often carry a middle name between the given
  name and the family name, traditionally the mother's maiden surname,
  and their bearers count it with their given names: ``"Maria Santos
  Reyes"`` has family ``Reyes``, which the switch reads as ``Santos
  Reyes``. Among ORCID's researchers in the Philippines it breaks about
  four names in ten and mends about one in a hundred.

The counts behind the last two are in
``docs/design/decisions/O6-two-family-names.md``.

What it reports
~~~~~~~~~~~~~~~

The parser reports nothing for the names the switch moves: the shape it
reads is the same either way.

Keeping a given name out of the family
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A given name standing before the family is most of what the switch gets
wrong, as in ``"José Luis Pérez"``. Words that are given names and
rarely surnames tell the two shapes apart, so the switch leaves a word
listed in the lexicon's ``given_names`` where it stands, under any
``name_order``.

The field is empty by default, so you supply the list for your data,
or choose ``locales.ES``, which turns the switch on and carries 1,000
Spanish given names, a name written with ñ listed with n too
(``locales.ES_AR``, for Argentine names, carries about 5,000; see
:ref:`spanish-portuguese-titles`), or ``locales.PT_BR`` or
``locales.PT_PT``, which carry about 700 Portuguese ones, a name
written with ç listed with c too (see
:ref:`portuguese-two-family-names`). An entry written without accents
matches the word with them:

.. doctest::

    >>> from nameparser import Lexicon
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

.. _kaur-singh:

Kaur and Singh
~~~~~~~~~~~~~~

``two_family_names`` and ``two_given_names`` both leave alone the Sikh
names Kaur and Singh, given to every Sikh woman and man and written
after the personal name: ``"Harpreet Kaur Dhillon"`` keeps middle
``Kaur`` under either switch, as it does by default.

.. _two-given-names:

Names with a compound given name
--------------------------------

Turn on ``two_given_names`` when the people in your data carry a given
name of two words and no middle name, and only then:
:ref:`What it costs <two-given-names-cost>` shows what it does to a
name that has a middle name.

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

The switch leaves Kaur and Singh as middle names (see
:ref:`kaur-singh`).

.. _two-given-names-chinese:

Chinese given names written as two words
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Singapore and Malaysia often write the two syllables of a Chinese given
name as two words, family name first (:ref:`name-order`). Under
``FAMILY_FIRST`` alone the second syllable is a middle name; with
``two_given_names`` on too the given name keeps both:

.. doctest::

    >>> tan = family_first.parse("Tan Wei Ming")
    >>> tan.family, tan.given, tan.middle
    ('Tan', 'Wei', 'Ming')
    >>> two_syllables = Parser(policy=Policy(name_order=FAMILY_FIRST,
    ...                                      two_given_names=True))
    >>> tan_two = two_syllables.parse("Tan Wei Ming")
    >>> tan_two.family, tan_two.given, tan_two.middle
    ('Tan', 'Wei Ming', '')

For a list written family first throughout, ``Parser.suggest`` decides
the order. It does not suggest ``two_given_names``, so add that
yourself:

.. doctest::

    >>> chinese_list = ["Tan Kok Leong", "Lim Boon Keat", "Ong Siew Ting",
    ...                 "Goh Wei Jie", "Teo Boon Leong", "Koh Siew Ting",
    ...                 "Chen Kok Keat", "Wang Wei Jie"]
    >>> Parser().suggest(chinese_list).patch
    PolicyPatch(name_order=FAMILY_FIRST)

A list that mixes the two orders needs the order from elsewhere (see
:ref:`mixed-name-order`).

Given names written with a particle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A given name a particle completes, such as María del Carmen, reads
whole too. Where the particle's words would otherwise run on into the
family, the parser reads them as a middle name, with or without the
switch, if the vocabulary marks the word behind the particle as a given
name written there (``after_particle``), and the switch then takes them
into the given name:

.. doctest::

    >>> parse("María del Carmen García").middle
    'del Carmen'
    >>> carmen = two_given.parse("María del Carmen García")
    >>> carmen.given, carmen.family
    ('María del Carmen', 'García')
    >>> two_given.parse("Maria do Carmo Silva").family
    'do Carmo Silva'

Which words are marked:

- **By default**, words from Spain and Spanish-speaking America
  (``del Carmen``, ``de los Ángeles``, ``del Mar``, ``del Pilar``), and
  from Portugal and Brazil (``de Lurdes``, ``das Graças``,
  ``de Cássia``, ``de Tarso``). They were chosen by how ORCID
  researchers filled their own name boxes; the criterion is in
  ``docs/design/decisions/P10-given-name-a-particle-completes.md``.
- **Under** ``locales.PT``, ``locales.PT_BR`` **and** ``locales.PT_PT`` **only**, a
  Portuguese word too rare to measure (``da Piedade``; see
  :ref:`language-packs`).
- **Not marked**: a phrase too often a surname, as Portuguese
  ``do Carmo`` is, stays the family, the same shape as ``"João da Silva
  Santos"``, and so does one opening with a saint (``"Domingo Santa
  María González"``).

To mark a word of your own, add it with ``Lexicon.default().add("carmo",
kind="given", after_particle=True)``, which moves the default reading
too.

.. _two-given-names-cost:

What it costs
~~~~~~~~~~~~~

Turn it on only for data written this way:

- **A name with a middle name.** Under the switch every name whose
  second given word is a middle name gains it in the given name
  (``"John Quincy Adams"`` gives given ``John Quincy``).
- **A form with a middle-name box.** People filling one split their
  names the other way. Among the UK company register's Spanish filers,
  about a third of names agree in every box by default and half as many
  with this switch on; with ``two_family_names`` on, four in five agree
  without this switch and little more than half with it
  (``docs/design/decisions/O7-two-given-names.md`` has the table).

What it reports
~~~~~~~~~~~~~~~

``middle`` keeps its meaning either way, the given part's words after
the given name; the switch moves no word anywhere else and reports
nothing.

.. _initials-as-family:

Names ending in initials that are the family name
-------------------------------------------------

Turn on ``initials_as_family`` when the letters ending the names in
your data stand for the family name, and only then (see
:ref:`What it costs <initials-as-family-cost>`). The Nepali pack, ``locales.NE``, turns it on, and
``Parser.suggest`` suggests it for a list whose names repeat one run of
letters (see :ref:`suggest-settings`).

In South India, Sri Lanka, Bangladesh and Nepal the letters written
after a given name often stand for the family's name, the father's name
or the place the family comes from, and the bearer treats them as the
family name: ``Lakshmi R S``, or ``Ram Bahadur B K``, where ``B K`` is
the surname Bishwakarma written short. The default reads those letters
as a middle and a family initial, the English convention:

.. doctest::

    >>> lakshmi = parse("Lakshmi R S")
    >>> lakshmi.middle, lakshmi.family
    ('R', 'S')

``initials_as_family=True`` reads the letters together as the family
name, under the default given-first order. One letter is the family
already, and letters before or inside a name, the given part after a
family comma and a name read family-first are left as they are:

.. doctest::

    >>> letters = Parser(policy=Policy(initials_as_family=True))
    >>> letters.parse("Lakshmi R S").family
    'R S'
    >>> letters.parse("Ram Bahadur B. K.").middle
    'Bahadur'
    >>> letters.parse("Lakshmi, R S").family
    'Lakshmi'

.. _initials-as-family-cost:

What it costs
~~~~~~~~~~~~~

Turn it on by hand only for data written this way. The same string is
two other things in many lists:

- **A middle and a family initial** (``Melanie J D``).
- **A byline written surname first** in a bibliography
  (``Huntley R P``), for which ``name_order=FAMILY_FIRST`` is the
  setting.

On ORCID researchers' credit names checked against the names they
filed, a spaced run of letters ending a name was a byline about three
times in four, the family about one time in six, and a middle and a
family initial rarely (the counts are in
``docs/design/decisions/O8-letters-ending-a-name-as-its-family.md``).

What it reports
~~~~~~~~~~~~~~~

The switch reports nothing. Without it, a name of one word followed by
nothing but initials reports the fork as an ``order`` ambiguity. It
names no ``alternative``: the other reading lays out the whole name,
the word in front as the family, which ``name_order=FAMILY_FIRST``
reads:

.. doctest::

    >>> [a.kind.value for a in parse("Kavitha S").ambiguities]
    ['order']
    >>> parse("Kavitha S").ambiguities[0].alternative is None
    True
    >>> letters.parse("Kavitha S").ambiguities
    ()

.. _capitals-as-family:

Family names written in capitals
--------------------------------

Turn on ``capitals_as_family`` when your source writes every family
name in capitals, and only then (see
:ref:`What it costs <capitals-as-family-cost>`). ``Parser.suggest`` suggests it for a list whose names write the family
in capitals (see :ref:`Settings for a list of names
<suggest-capitals>`).

Some lists write every family name in capitals: France's register of
elected officials (``DUPONT Jean``), Hong Kong's Legislative Council
(``CHAN Kin-por``, ``Jeffrey LAM Kin-fung``) and the Turkish,
Azerbaijani and Kazakh parliaments; Japanese names written in Latin
script are often written so too (``YAMAMOTO Yukio``).
The capitals mark the family name where position cannot: the same list
puts it first, last or in the middle, and writes two surnames as one.
The default reads by position, so a family name written first is read
as the given name, and a second surname as a middle name:

.. doctest::

    >>> dupont = parse("DUPONT Marie")
    >>> dupont.given, dupont.family
    ('DUPONT', 'Marie')
    >>> parse("Ayla BURSALI AKSOY").middle
    'BURSALI'

``capitals_as_family=True`` reads the run of words in capitals as the
family name wherever it stands, and the other words in their written
order, the first the given name:

.. doctest::

    >>> capitals = Parser(policy=Policy(capitals_as_family=True))
    >>> capitals.parse("DUPONT Marie").family
    'DUPONT'
    >>> capitals.parse("Ayla BURSALI AKSOY").family
    'BURSALI AKSOY'
    >>> lam = capitals.parse("Jeffrey LAM Kin-fung")
    >>> lam.given, lam.middle, lam.family
    ('Jeffrey', 'Kin-fung', 'LAM')

``capitalized()`` leaves such a name as written, since it is in mixed
case; ``capitalized(force=True)`` recases the family too. The switch
cannot be set with ``unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE``,
which reads an unlisted capitals word ending a name as a credential.

What it reads
~~~~~~~~~~~~~

- **A capitals word** has two or more capital letters and nothing but
  letters, apostrophes and hyphens (``O'BRIEN`` and ``McDONALD`` count,
  ``DR.``, ``N/A`` and ``J-P`` do not).
- **The run** joins across particles and conjunctions
  (``Aude BROSSARD de VILLEMONT``), and takes a lowercase particle
  written right before it (``Jean de LA FONTAINE``). A run of particles
  alone is none, and where a name word divides two runs, the last is
  the family.
- **The capitals outrank a credential or title reading**, so
  ``Hugo LAC`` gives family ``LAC`` and ``DOYEN Hugo`` family
  ``DOYEN``. A listed credential or numeral in capitals ending the
  name still comes off where a capitals word before it, no particle,
  conjunction, numeral or marker, is left to be the family, before the
  family is chosen (``Marie GRAJALES III`` and ``DUPONT Marie MBA`` give
  suffix ``III`` and ``MBA``, ``Marie MA MBA`` family ``MA``), and a
  roman numeral alone stays the suffix (``John Smith III``). Under a
  patronymic rule its marker is no capitals word where another one is
  left (``OGLU``).

What it leaves alone
~~~~~~~~~~~~~~~~~~~~

- **A name with no lowercase letter** outside its titles, its suffixes
  and the particles and conjunctions written in lowercase
  (``MARIE DUPONT``, ``Dr. MARIE DUPONT``, ``MARIE de DUPONT``). A
  particle written with a capital is a name word, so ``MORRISON Van``
  is read.
- **The words after the first comma**, so a family comma still names
  the family and a credential after a comma stays one.

.. doctest::

    >>> capitals.parse("MARIE DUPONT").given
    'MARIE'
    >>> capitals.parse("Dupont, MARIE").family
    'Dupont'
    >>> chan = capitals.parse("Hon CHAN Kin-por, GBS, JP")
    >>> chan.family, chan.suffix
    ('CHAN', 'GBS, JP')

.. _capitals-as-family-cost:

What it costs
~~~~~~~~~~~~~

Turn it on only for data written this way. Elsewhere capitals also
write:

- **A given name**: ``ANNA Smith`` gives family ``ANNA``.
- **A credential with no comma before it**: ``John Smith MD`` gives
  family ``MD``.
- **Joined initials**: ``Jan GM Brouwer`` gives family ``GM``.
- **A title written in capitals, with no full stop, where no other
  word of the name is in capitals**: ``DR Anna Berg`` gives family
  ``DR``, middle ``Berg``. A title that can also open a surname, as
  ``ST`` or ``FREIHERR`` can, stays the title. Such a name does not write its
  family name in capitals, so it is not in the format the switch is
  for; where the family is in capitals too, the title keeps its place
  (``DR Anna BERG`` gives title ``DR``, family ``BERG``).

In ORCID researchers' own boxes, where one box holds the words in
capitals, it is the family box nine times in ten (the counts are in
``docs/design/decisions/O9-words-in-capitals-as-the-family.md``).

What it reports
~~~~~~~~~~~~~~~

The switch adds no report of its own. Where it acts it drops the
reports the capitals settle:

- one asking which field a word of the run, or a word the peel took,
  takes;
- every ``given-or-family``, ``particle-or-given`` and ``order``
  report, the capitals having said where the family is.

A report about a title or a suffix on another word stays.

.. _brackets:

Nicknames, maiden names, and brackets
--------------------------------------

Maiden markers
~~~~~~~~~~~~~~

A maiden name is usually announced by a marker word, and then it needs
no brackets and nothing configured:

.. doctest::

    >>> parse("Jane Smith née Jones").maiden
    'Jones'

:ref:`nicknames-and-maiden-names` in :doc:`shapes` covers how the
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
phrase, not word by word; see :ref:`Vocabulary: Lexicon <vocabulary-lexicon>`.

How a bracketed clause is read
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A delimiter pair carries no meaning of its own, so what a clause
enclosed in one reads as is settled in steps, and the pair is asked
last:

1. **A clause of credentials, generations or titles** is taken first
   and set apart from the name: each word becomes the suffix or the
   title its vocabulary makes it, and the name around it reads as it
   would beside a nickname. A few such words stay a nickname all the
   same: a bare ``Sir``, ``Mrs`` or ``Junior``, and a credential
   written as initials before a name word (``Justin (JP) Stearns``);
   :ref:`nicknames-and-maiden-names` has the cases. Other content
   ending in a period loses its brackets and parses as if it had been
   written bare.
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~

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
---------------------------------

A comma is the usual separator between post-nominals, but sources write
others. A few are read with no configuration, any other can be
declared, and a credential joined to another, or split by a space,
needs neither.

Separators read without configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

.. _lenient-comma-suffixes:

A single letter after a comma
-----------------------------

Set ``lenient_comma_suffixes=False`` when your data writes a surname of
two words before a comma and the initial of a given name after it.

``"Vega Ruiz, V"`` can be Vega Ruiz the fifth, or the surname ``Vega
Ruiz`` with a given-name initial. The field is on by default and reads
the first: a suffix word shaped like an initial (``V``, ``I``),
alone after a comma or followed only by other suffixes (``V PhD``),
behind two or more name words, is the suffix. ``False``
reads it as a given-name initial instead:

.. doctest::

    >>> fifth = parse("Vega Ruiz, V")
    >>> fifth.given, fifth.family, fifth.suffix
    ('Vega', 'Ruiz', 'V')
    >>> comma_strict = Parser(policy=Policy(lenient_comma_suffixes=False))
    >>> initial_v = comma_strict.parse("Vega Ruiz, V")
    >>> initial_v.given, initial_v.family
    ('V', 'Vega Ruiz')
    >>> comma_strict.parse("vega ruiz, v").given
    'v'
    >>> comma_strict.parse("Vega Ruiz, III").suffix
    'III'

``"john smith, v"`` reads the same way as ``"John Smith, V"`` under
``False``, since a name written all in one case reads as its capitals.
Multi-letter suffixes (``III``, ``MD``) are unaffected. Behind a single
word the letter is the given name under either setting
(``"Smith, V"``), and so is one with a name word after it
(``"Vega Ruiz, V Maria"``).

.. _unlisted-credentials:

Credentials the vocabulary doesn't list
----------------------------------------

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
field reads as a credential. The capitals give way to one more: written
undotted, the letters are a credential when credentials follow them and
nothing else stands beside them (``"Jane Doe, BM PhD"``), where the
dotted spelling keeps its given name (``"John Smith, A.B. Ph.D."``).

Either spelling, in capitals in a name of mixed case, is a credential
when it stands alone in its part and a later part holds nothing but
credentials the vocabulary lists as that alone (``"Jane Doe, BM,
PhD"``, ``"Jane Doe, B.M., PhD"``). A title in front of them says the
opposite:

.. doctest::

    >>> parse("John Smith, PhD X.Y.").suffix
    'PhD X.Y.'
    >>> parse("John Smith, PhD MJ").suffix
    'PhD MJ'
    >>> parse("García Márquez, MJ XYZ").suffix
    'MJ XYZ'
    >>> parse("Jane Doe, BM PhD").suffix
    'BM PhD'
    >>> parse("Jane Doe, BM, PhD").suffix
    'BM, PhD'
    >>> parse("Jane Doe, B.M., PhD").suffix
    'B.M., PhD'
    >>> parse("John Smith, A.B. Ph.D.").given_names
    'A.B.'
    >>> cred = parse("García Márquez, Ms G.J.")
    >>> cred.title, cred.given_names
    ('Ms', 'G.J.')

.. _dotted-credentials:

Dotted acronyms
~~~~~~~~~~~~~~~

``unlisted_dotted_suffixes`` is on by default. It reads a token of two
or more period-separated chunks as a credential at the end of a name,
right after a comma behind two or more name words, at the end of the
given part after a family comma, and at the end of a maiden marker's
clause. Case is irrelevant; the periods are the signal.
With nothing to spare in front of it, the word stays a name.

At the end
of a name, given part or clause, either reading reports the fork as a
``suffix-or-name`` ambiguity, so a record that reads wrong can still be
found; right after a comma behind a full name, the credential reading
is taken silently, save for two letters that only other such pairs,
or a later part, speak for (above):

.. doctest::

    >>> cred = parse("John Smith X.Y.Z.")
    >>> cred.family, cred.suffix
    ('Smith', 'X.Y.Z.')
    >>> parse("Jack X.Y.Z.").family
    'X.Y.Z.'
    >>> cred = parse("Doe, John X.Y.Z.")
    >>> cred.given, cred.suffix
    ('John', 'X.Y.Z.')
    >>> parse("Doe, X.Y.Z.").given_names
    'X.Y.Z.'
    >>> cred = parse("Jane Doe nee Smith X.Y.Z.")
    >>> cred.maiden, cred.suffix
    ('Smith', 'X.Y.Z.')
    >>> cred = parse("John Smith, X.Y.Z.")
    >>> cred.suffix, cred.ambiguities
    ('X.Y.Z.', ())

Five things are not this shape:

- **A token the vocabulary already knows** (``M.A.``, ``Ph.D.``) is
  read by the vocabulary, save capital letters run together right after
  a one-word surname and a comma, which are the given name whatever
  they spell, as ``Doe, X.Y.Z.`` is, unless a credential other than a
  generation stands beside them (``"Jansen, J.P."`` gives given ``J.``,
  middle ``P.``, the credential reported; ``"Jansen, J.P. PhD"`` keeps
  suffix ``J.P. PhD``).
- **A single trailing period** is how any word is abbreviated, so
  ``"John Smith Xyz."`` keeps family ``Xyz.``.
- **A digit anywhere** refuses it, since every chunk must be alphabetic
  (``"John Smith 1.4"`` keeps family ``1.4``).
- **A script with no period abbreviations of its own** refuses it too
  (``"John Smith 田.中."`` keeps family ``田.中.``).
- **Two single letters, each with its period,** are how initials are
  written, and how some surnames are, such as the Nepali ``B.K.``: in a
  script with capitals they stay a name word wherever they end a name,
  given part or clause, and still report the fork, while three letters
  or more are a credential as before. Right after a comma they are the
  exception above:

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
~~~~~~~~~~~~~~

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^

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
^^^^^^^

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
-------------------------------------

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
