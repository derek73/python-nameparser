Behavior: Policy
=================

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
     - Reads the last two name words as the family name (the first
       two under a family-first order), for data
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
   * - ``initials_as_family``
     - ``bool``
     - Reads two or more single letters ending a name as its family
       name (``Lakshmi R S``), for South Asian data where the letters
       stand for a family name. Defaults to ``False``. See
       :ref:`initials-as-family`.
   * - ``capitals_as_family``
     - ``bool``
     - Reads the words a name writes in capitals as its family name
       (``DUPONT Jean``), for data whose source writes every family
       name in capitals. Defaults to ``False``. See
       :ref:`capitals-as-family`.
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

    >>> from nameparser import Lexicon
    >>> from nameparser import Policy, PolicyPatch
    >>> Policy().patched(PolicyPatch(middle_as_family=True))
    Policy(middle_as_family=True)

.. _name-order:

Family-first name order
------------------------

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
------------------------------------------------

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

:ref:`Words that are also ordinary names <ambiguous-words>` covers dropping a word from a
vocabulary, or moving one between those two sets.

.. _lone-name-word:

Names written as one word
-------------------------

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
John"`` given ``John``), a nickname or maiden name beside it, a family
comma (``"Anh, Jr."`` is family ``Anh``, ``", Anh"`` given ``Anh``), and a name its script reads family-first: Han, Hangul, or kana other than
katakana alone (``"みなみ"`` is family ``みなみ``). Through 2.x
the field followed ``name_order``, so a family-first order read a
lone word as the family name.

.. _two-family-names:

Names with two family names
---------------------------

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
--------------------------------

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

.. _initials-as-family:

Names ending in initials that are the family name
-------------------------------------------------

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

The Nepali pack, ``locales.NE``, turns it on, and ``Parser.suggest``
suggests it for a list whose names repeat one run of letters (see
:ref:`suggest-settings`). Turn it on by hand only for data written this
way: the same string is a middle and a family initial in many lists
(``Melanie J D``) and a byline written surname first in a bibliography
(``Huntley R P``, for which ``name_order=FAMILY_FIRST`` is the setting).
Measured on ORCID researchers' credit names checked against the names
they filed, a spaced run of letters ending a name was the family 66
times, a middle and a family initial 11 times and a byline 302 times
(2026-11-11). The switch reports nothing. Without it, a name of one
word followed by nothing but initials reports the fork as an ``order``
ambiguity. It names no ``alternative``: the other reading lays out the
whole name, the word in front as the family, which
``name_order=FAMILY_FIRST`` reads:

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

What it reads:

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

What it leaves alone: a name with no lowercase letter outside its
titles, its suffixes and the particles and conjunctions written in
lowercase (``MARIE DUPONT``, ``Dr. MARIE DUPONT``, ``MARIE de
DUPONT``) -- a particle written with a capital is a name word
(``MORRISON Van`` is read) -- and the words after the first comma, so a family comma still names the family
and a credential after a comma stays one:

.. doctest::

    >>> capitals.parse("MARIE DUPONT").given
    'MARIE'
    >>> capitals.parse("Dupont, MARIE").family
    'Dupont'
    >>> chan = capitals.parse("Hon CHAN Kin-por, GBS, JP")
    >>> chan.family, chan.suffix
    ('CHAN', 'GBS, JP')

Turn it on only for data written this way. Elsewhere capitals also
write a given name (``ANNA Smith`` gives family ``ANNA``), a credential
with no comma before it (``John Smith MD`` gives family ``MD``), or
joined initials (``Jan GM Brouwer`` gives family ``GM``). Measured on
ORCID researchers' own boxes, where one box holds the words in
capitals, it is the family box nine times in ten (2026-11-11). The
switch adds no report of its own. Where it acts it drops the reports the
capitals settle: one asking which field a word of the run, or a word the
peel took, takes; and every ``given-or-family``, ``particle-or-given``
and ``order`` report, the capitals having said where the family is. A
report about a title or a suffix on another word stays.
``capitalized()`` leaves the name as written, since it is in mixed
case; ``capitalized(force=True)`` recases the family too. It cannot be
set with
``unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE``, which reads an
unlisted capitals word ending a name as a credential. ``Parser.suggest``
suggests it for a list whose names write the family in capitals (see
:ref:`Settings for a list of names <suggest-capitals>`).

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
phrase, not word by word; see :ref:`Vocabulary: Lexicon <vocabulary-lexicon>` above.

How a bracketed clause is read
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
dotted spelling keeps its given name (``"John Smith, A.B. Ph.D."``). A
title in front of them says the opposite:

.. doctest::

    >>> parse("John Smith, PhD X.Y.").suffix
    'PhD X.Y.'
    >>> parse("John Smith, PhD MJ").suffix
    'PhD MJ'
    >>> parse("García Márquez, MJ XYZ").suffix
    'MJ XYZ'
    >>> parse("Jane Doe, BM PhD").suffix
    'BM PhD'
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
    >>> parse("Doe, X.Y.Z.").given_names
    'X.Y.Z.'
    >>> cred = parse("Jane Doe nee Smith X.Y.Z.")
    >>> cred.maiden, cred.suffix
    ('Smith', 'X.Y.Z.')
    >>> cred = parse("John Smith, X.Y.Z.")
    >>> cred.suffix, cred.ambiguities
    ('X.Y.Z.', ())

Five things are not this shape. A token the vocabulary already knows
(``M.A.``, ``Ph.D.``) is read by the vocabulary, save capital letters
run together right after a one-word surname and a comma, which are the
given name whatever they spell, as ``Doe, X.Y.Z.`` is, unless a
credential other than a generation stands beside them (``"Jansen, J.P."`` gives given ``J.``,
middle ``P.``, the credential reported; ``"Jansen, J.P. PhD"`` keeps
suffix ``J.P. PhD``). A single trailing
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
