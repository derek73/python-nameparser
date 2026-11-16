.. _suggest-settings:

Settings for a list of names
============================

A list of names is usually written in one convention: a registry gives
every family name first, a mailing list every family name last. A
single name often cannot show which: in ``Taylor Morgan`` either word
is a common given name and a common surname, so neither the parser nor
a reader can place it. A whole list can: most of its names carry some
evidence, and the evidence agrees.

``Parser.suggest()`` reads a list you declare to be one group (one
source, one convention) and returns a :class:`~nameparser.Suggestion`:
the settings its names agree on, and a parser that reads with them.

.. doctest::

    >>> from nameparser import Parser
    >>> listing = ["Taylor Morgan", "Kim Minjun", "Wang Xiaoming",
    ...            "Nguyen Anh", "Garcia Emily"]
    >>> suggestion = Parser().suggest(listing)
    >>> suggestion.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> Parser().parse("Taylor Morgan").given
    'Taylor'
    >>> suggestion.parser.parse("Taylor Morgan").given
    'Morgan'

Four names vote for family first: ``Kim``, ``Wang`` and ``Nguyen`` by
the romanized surname in front, ``Garcia Emily`` by the common given
name at the end; ``Wang Xiaoming`` carries both, so each signal's row
counts it. ``Taylor Morgan`` gives no evidence: it is read family
first because the list is, and nothing in the name can confirm that.

Each name votes on its order from the evidence it carries
(:ref:`suggest-evidence`), and the group decides the order where enough
of its names agree (:ref:`suggest-deciding`). Three more settings are
decided the same way, each by its own evidence: a patronymic rule
(:ref:`suggest-patronymics`), ``initials_as_family``
(:ref:`suggest-initials`) and ``capitals_as_family``
(:ref:`suggest-capitals`). Every setting the votes do not decide keeps
the base parser's value.

.. _suggest-how-many:

How many names to give it
-------------------------

Give it names from one source, written one way, and a few hundred of
them at most:

- **Under five names** often gets no suggestion. That is safe: a list
  short of evidence keeps the parser it was given.
- **Fifty names** settles most kinds of list.
- **A few hundred** settles nearly every kind measured. More rarely
  helps, and can hurt.

For a large dataset, take a sample from each source instead of passing
everything:

.. doctest::

    >>> import random
    >>> registry = ["Kim Minjun", "Wang Xiaoming", "Nguyen Anh",
    ...             "Garcia Emily", "Taylor Morgan"] * 20_000
    >>> sample = random.Random(0).sample(registry, k=300)
    >>> Parser().suggest(sample).patch
    PolicyPatch(name_order=FAMILY_FIRST)

A sample is quicker, a suggestion costing about what parsing the same
names does, but that is not the main reason. A very long list can be
read less well than a sample of it, because the order is decided among
the names that vote, and in a list where few names vote a handful of
stray votes weigh more the longer the list is.

The one kind of list measured that more names kept helping is bylines
written initials first (``AM Hoy``) under a family-first base, where
so few names vote that a sample of a few hundred often decides nothing.
Where you know how such a list is written, set ``name_order`` yourself.

A list that mixes sources written differently works against itself.
Split it by source and ask once for each. :ref:`suggest-limits` gives
the sizes measured for each kind of list.

.. _suggest-report:

Reading the result
------------------

``suggestion.parser`` is the base parser with ``suggestion.patch``
applied, so the base is never changed. ``suggestion.evidence`` holds a
:class:`~nameparser.SettingEvidence` for each setting considered and
``suggestion.names`` a :class:`~nameparser.NameEvidence` for each name,
in input order. ``disagreeing()`` lists the names whose vote is against
a decided setting, the ones to check by hand
(:ref:`suggest-disagreeing`).

``print(suggestion)`` writes a report of each setting's evidence and
the names that disagree with it:

.. doctest::

    >>> print(suggestion)
    Suggested for 5 names (base: Parser(Lexicon(default), Policy())):
      name_order  FAMILY_FIRST  4 for, 0 against, 1 no evidence
          surname FAMILY_FIRST  3
          given-name FAMILY_FIRST  2
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      capitals_as_family  unchanged (False)  5 for, 0 against, 0 no evidence

The report reads as follows:

- **The first line** counts the names and shows the base parser.
- **One line for each setting** gives its value under the suggested
  parser. A value standing alone (``FAMILY_FIRST``) was decided by the
  list and changes the base; one followed by ``(as the base)`` was
  decided and is what the base already had; ``unchanged (...)`` was
  not decided, and shows the base's value, which stays.
- **The counts** on that line are of names, for and against the value
  the suggested parser has. So a list left with the capitals switch
  off counts its names in mixed case with no word in capitals as
  ``for`` (``5 for`` above), and its names in capitals as ``against``.
- **no evidence** counts the names that carry none on that setting. A
  line that says only ``no evidence`` had no name for, against or
  contested.
- **contested** is a fourth count, printed where it is not zero: the
  names whose own evidence points both ways on the order (in ``Kim
  SMITH`` the surname in front says family first and the capitals at
  the end say family last). A contested name casts no order vote and
  never disagrees on the order.
- **The indented rows** under ``name_order`` and ``patronymic_rules``
  count the names by kind of evidence and the value it votes for. A
  name carrying two kinds is in two rows (``Wang Xiaoming`` above), so
  the rows can add up to more than the names for.
- **An indented sentence**, where one follows, is a note saying why
  the setting was decided or left as it was.
- **A last line**, ``disagreeing (1): ...``, names the first five of
  the names against a decided setting, where there are any.

For each setting the four counts add up to the number of names. They
are the ``votes_for``, ``votes_against``, ``contested`` and
``no_evidence`` of its :class:`~nameparser.SettingEvidence`, whose
``by_signal`` holds the indented rows and ``note`` the sentence.

.. _suggest-disagreeing:

Names that disagree with the list
---------------------------------

A list from one source can still hold a name written the other way
round. Here ``Emily Clark`` puts its given name first, votes against
the list, and is listed by ``disagreeing()``. Check such a name by
hand: the suggested parser reads it the way the rest of the list is
written, so it takes ``Clark`` for the given name:

.. doctest::

    >>> mixed = Parser().suggest(listing + ["Emily Clark"])
    >>> [entry.text for entry in mixed.disagreeing()]
    ['Emily Clark']
    >>> mixed.parser.parse("Emily Clark").given
    'Clark'

The report counts it as ``against`` and names it on its last line:

.. doctest::

    >>> print(mixed)
    Suggested for 6 names (base: Parser(Lexicon(default), Policy())):
      name_order  FAMILY_FIRST  4 for, 1 against, 1 no evidence
          surname FAMILY_FIRST  3
          given-name FAMILY_FIRST  2
          given-name GIVEN_FIRST  1
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      capitals_as_family  unchanged (False)  6 for, 0 against, 0 no evidence
      disagreeing (1): Emily Clark

.. _suggest-deciding:

When the list decides the order
-------------------------------

Each setting is decided only where enough names carry its evidence
and enough of them agree:

.. list-table::
   :header-rows: 1
   :widths: 22 30 34 14

   * - Setting
     - Fewest names
     - Share they must be
     - Section
   * - ``name_order``
     - 2 voting for one end
     - more than two thirds of the names that cast an order vote
     - this one
   * - ``patronymic_rules``
     - 5 carrying one rule's patronymic
     - more than four in five of the names that cast any vote
     - :ref:`suggest-patronymics`
   * - ``initials_as_family``
     - 2 ending in one run of letters
     - at least half of the names ending in a run of letters
     - :ref:`suggest-initials`
   * - ``capitals_as_family``
     - 2 writing the family name in capitals of four letters or more
     - more than two thirds of the names with evidence either way
     - :ref:`suggest-capitals`

The group decides ``name_order`` when at least two names vote for one
end and they are more than two thirds of the names that cast an order
vote: a tie, or two names against one, decides nothing. A name with no
evidence on the order, and a name whose evidence is contested, casts no
order vote and is outside that share.

Two is the floor, not what a typical list needs. Two names decide a
list only where no other name votes against them, and how many names a
list needs before enough of them vote depends on what its names carry:
:ref:`suggest-limits` gives the sizes measured, from 5 names to 50.

When it suggests nothing
~~~~~~~~~~~~~~~~~~~~~~~~

A setting whose votes fall short of its threshold above keeps the
base parser's value rather than a guess, whatever the other settings
decide. Where every setting falls short, or no name in the list
carries evidence, the patch is empty. None of these
names holds a romanized surname, a given name that is rarely a
surname, or any other evidence on the order:

.. doctest::

    >>> undecided = Parser().suggest(["Taylor Morgan", "Jordan Casey",
    ...                               "Avery Quinn"])
    >>> undecided.patch
    PolicyPatch()

An empty patch means only that nothing differs from the base: the
list may have shown no order, or shown the base's own. Print the
suggestion to see which. The ``name_order`` line says ``no evidence``,
gives the votes that fell short, or shows the base's order decided,
``(as the base)``. (The ``capitals_as_family`` line counts names in
mixed case as ``for`` the switch staying off, :ref:`suggest-report`.)

.. doctest::

    >>> print(undecided)
    Suggested for 3 names (base: Parser(Lexicon(default), Policy())):
      name_order  unchanged (GIVEN_FIRST)  no evidence
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      capitals_as_family  unchanged (False)  3 for, 0 against, 0 no evidence

Then, where you know how the list is written, set the order yourself
(:ref:`name-order`):

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Policy
    >>> declared = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> declared.parse("Taylor Morgan").given
    'Morgan'

.. _suggest-evidence:

What a name votes on
--------------------

Each name votes on its order from the evidence it carries:

- **A family name written in capitals** at one end of a name in mixed
  case (``Mary SMITH``). A word of two or three
  capitals is as often joined initials (``AM Hoy``, ``Armitage JO``)
  as a short surname (``NG Emily``, ``Zhi LI``), so ending the name,
  or opening it with no word in capitals after it (``DE SOUZA Maria``
  still votes), it casts no capitals vote. Nor does it vote as a
  surname: a name opening in one casts no surname vote, and neither
  does a name ending in one that is a listed surname (``Zhou NG``),
  whose first word is usually the given name.
- **A trailing initial** (``Smith J.``), where at least three names,
  and 60% of the list's names that hold a name word, end in initials no
  other evidence in the same name contradicts, as a bibliography's do.
  Names with a comma, blanks and names of nothing but titles or marks
  leave the count. The floor is there because letters ending a name
  are not always initials (:ref:`suggest-initials`), so a short list
  of bylines may get no order suggestion: where you know a list is
  bylines, set ``name_order=FAMILY_FIRST`` yourself.
- **A lowercase particle** first or before the last word.
- **A common romanized Chinese, Korean or Vietnamese surname** as the
  first or last word.
- **A common given name that is rarely a surname** (``Emily``, not
  ``Taylor``) as the first or last word.

Each is read past the titles and post-nominals your parser's vocabulary
lists (``Dr.``, ``PhD``, ``Jr.``). A name with a comma states its own
order and does not vote, unless only post-nominals follow the comma
(``Kim Minjun, PhD``), and neither does a name of one word.

The evidence need not be a surname. Here the common given names at the
end decide the order, and ``Ellis Jordan``, which carries none, follows
them:

.. doctest::

    >>> by_given = Parser().suggest(["Parker Emma", "Reed Sophie", "Ellis Jordan"])
    >>> by_given.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> by_given.parser.parse("Ellis Jordan").given
    'Jordan'

.. _suggest-patronymics:

Lists with patronymics
----------------------

``suggest()`` turns a patronymic rule on (East Slavic or Turkic,
:class:`~nameparser.PatronymicRule`) for a list whose names carry the
father's name as a patronymic: Russian ``Petrovich`` and ``Ivanovna``,
Azerbaijani ``Huseyn oglu``. It is decided where at least five names
carry one rule's patronymic and they are more than four in five of the
names that cast any vote, on the order or on a patronymic.

Under the default parser a list written family name first reads its
patronymic as the family name; with the rule, each name is put back in
order and its patronymic set apart:

.. doctest::

    >>> registry = ["Sidorov Ivan Petrovich", "Volkov Pavel Sergeevich",
    ...             "Orlova Anna Ivanovna", "Zaitsev Oleg Nikolaevich",
    ...             "Belova Vera Andreevna"]
    >>> Parser().parse("Sidorov Ivan Petrovich").family
    'Petrovich'
    >>> slavic = Parser().suggest(registry)
    >>> slavic.patch
    PolicyPatch(patronymic_rules=frozenset({<PatronymicRule.EAST_SLAVIC: 'east-slavic'>}))
    >>> sidorov = slavic.parser.parse("Sidorov Ivan Petrovich")
    >>> sidorov.given, sidorov.family, sidorov.patronymic
    ('Ivan', 'Sidorov', 'Petrovich')

The order that comes with the rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Turkic rule is suggested alone: it reads a name written either way
round, so the order is left to the names' own votes. The East Slavic
rule reorders a name only under a given-first order, so what is
suggested with it depends on the base parser's order and on where the
list writes the patronymic, last (``Sidorov Ivan Petrovich``) or in
the middle (``Ivan Petrovich Sidorov``):

.. list-table::
   :header-rows: 1
   :widths: 30 38 32

   * - Base parser's order
     - The list writes the patronymic
     - Order suggested with the rule
   * - ``GIVEN_FIRST``
     - last or in the middle
     - none: the base's stays
   * - ``FAMILY_FIRST``
     - last in more names than in the middle
     - none: the base's stays
   * - ``FAMILY_FIRST``
     - in the middle in as many names, or more
     - ``GIVEN_FIRST``
   * - ``FAMILY_FIRST_GIVEN_LAST``
     - last or in the middle
     - ``GIVEN_FIRST``

.. doctest::

    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> family_first.suggest(registry).patch
    PolicyPatch(patronymic_rules=frozenset({<PatronymicRule.EAST_SLAVIC: 'east-slavic'>}))
    >>> spoken = ["Ivan Petrovich Sidorov", "Pavel Sergeevich Volkov",
    ...           "Anna Ivanovna Orlova", "Oleg Nikolaevich Zaitsev",
    ...           "Vera Andreevna Belova"]
    >>> family_first.suggest(spoken).patch
    PolicyPatch(name_order=GIVEN_FIRST, patronymic_rules=frozenset({<PatronymicRule.EAST_SLAVIC: 'east-slavic'>}))

The names' own order votes come before the table in two cases:

- **They decide a family-first order.** The rule never overrides it:
  the list gets the rule with that order, under which the rule
  reorders no name.
- **They decide given-first under a** ``FAMILY_FIRST`` **base.** The
  second row does not apply, and the list gets ``GIVEN_FIRST`` with
  the rule.

Where a ``FAMILY_FIRST`` base keeps its order, the rule reorders no
name there and fills the ``patronymic`` view. The names written the
other way, patronymic in the middle, get no given-first order, and the
note under ``patronymic_rules`` counts them.

What counts for and against
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **For**: a name carrying the decided rule's patronymic. A patronymic
  votes only where the rule can read it (three name words for East
  Slavic, three or four for Turkic).
- **Against**: a name carrying the other rule's patronymic, which
  ``disagreeing()`` lists. Where no rule is decided, a name carrying a
  patronymic the base has no rule for is counted against the value the
  base keeps.
- **No evidence**: every other name. The share is still taken of the
  names that cast any vote, and a name whose only vote was a trailing
  initial the list did not count (:ref:`suggest-evidence`) is among
  them; the note under ``patronymic_rules`` says how many.

A name carrying the East Slavic patronymic never disagrees on the
order where the rule is decided with a given-first order, since the
rule reorders it.

What the report shows
~~~~~~~~~~~~~~~~~~~~~

The ``patronymic_rules`` line has a row for each rule the names voted
for, and the ``name_order`` line a note where the rule decided the
order:

.. doctest::

    >>> [e.note for e in slavic.evidence if e.setting == "name_order"]
    ['the East Slavic rule reorders each name; it needs a given-first order']

.. _suggest-initials:

Lists that end names in letters
-------------------------------

``suggest()`` turns ``initials_as_family`` on (see
:ref:`initials-as-family`) for a list that ends its names in letters
that are the family name. South Asian lists often do, and repeat the
letters: Nepal's ``B K`` and ``K C`` are surnames written short.

The repeat is the evidence. The switch is decided where one run of
letters ends at least two of the list's names and at least half of the
names ending in a run of letters:

.. doctest::

    >>> Parser().parse("Ram Bahadur B K").family
    'K'
    >>> nepal = Parser().suggest(["Durga B K", "Sita B.K.", "Hari Thapa"])
    >>> nepal.patch
    PolicyPatch(initials_as_family=True)
    >>> nepal.parser.parse("Ram Bahadur B K").family
    'B K'

A list whose letters are its family casts no trailing-initial vote on
the order (:ref:`suggest-evidence`).

What counts for and against
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **For**: a name ending in a run of two or more single letters after
  a name word, written apart (``Durga B K``) or joined with full stops
  (``Sita B.K.``).
- **Against**: nothing. No name is evidence that letters are not a
  family name, so a group never turns the switch off. In the report a
  list left with the switch off counts its names ending in letters as
  ``against``, the report counting for and against the value kept.
- **No evidence**: every other name. Two or three capitals written
  together (``Durga BK``) are not a run of letters: a short surname is
  written the same way.

A base that reads names family first is suggested no change: letters
ending a name are never taken as its family there, so no name is read
for a run, and the report says so.

What the report shows
~~~~~~~~~~~~~~~~~~~~~

The note under ``initials_as_family`` names the letters:

.. doctest::

    >>> [e.note for e in nepal.evidence if e.setting == "initials_as_family"]
    ['2 of the 2 names ending in a run of letters end in B K']

.. _suggest-capitals:

Lists that write the family name in capitals
--------------------------------------------

``suggest()`` turns ``capitals_as_family`` on (see
:ref:`capitals-as-family`) for a list that writes its family names in
capitals (``Mary SMITH``), as France's administrative style and
several parliaments do, so the capitals mark the family name wherever
it stands. It is decided where at least two names, and more than two
thirds of the names with evidence either way, write their family in
capitals. The order is decided apart from it.

.. doctest::

    >>> capitals = Parser().suggest(["Mary SMITH", "Ruth HOLLIS", "Anna BERG"])
    >>> capitals.patch
    PolicyPatch(capitals_as_family=True)
    >>> Parser().parse("SMITH Mary").family
    'Mary'
    >>> capitals.parser.parse("SMITH Mary").family
    'SMITH'

What counts for and against
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each name counts for the switch, against it, or not at all:

- **For**: a name whose family name, read with the switch on, holds a
  word in capitals of four letters or more that is no listed
  credential. A surname your vocabulary also lists as a title counts
  for it where your parser reads it as the family (``Mary BISHOP``).
- **Against**: a name of two words or more in mixed case with no word
  in capitals, which a name is once its titles and post-nominals are
  read past (``DR Ann Berg``, ``Prof. Ann Berg``, ``John Smith FRCS``);
  and a name where the switch would move the family onto a word your
  parser reads as a title in that name (``MISS Ann Berg``, and
  ``BISHOP Mary``, whose surname opens the name and is taken for a
  title). Such a name disagrees with a decided switch.
- **No evidence**: every other name. Two or three capitals are as
  often initials as a short surname (``AM Hoy``, ``Zhi LI``; see
  :ref:`suggest-evidence`), and a name wholly in one case shows
  nothing.

A group never turns the switch off, and a base reading an unlisted word
in capitals as a credential everywhere
(``unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE``) is suggested no
change, the two settings being opposite readings of the same word.

What the report shows
~~~~~~~~~~~~~~~~~~~~~

The note under ``capitals_as_family`` counts the names on each side:

.. doctest::

    >>> [e.note for e in capitals.evidence if e.setting == "capitals_as_family"]
    ['3 of the 3 names with evidence write the family in capitals of 4 letters or more, 0 in mixed case with no capitals']

A list left with the switch off shows no note unless a name writes its
family in capitals, and counts its names in mixed case as ``for``
(:ref:`suggest-report`).

.. _suggest-packs:

Choosing a language pack
------------------------

A suggestion never chooses a language pack. It proposes the four
``Policy`` settings above (``name_order``, ``patronymic_rules``,
``initials_as_family`` and ``capitals_as_family``) and leaves the
vocabulary as the base parser has it. The words a pack turns on, and
its other rules (two family names for Spanish, dividing a Chinese
surname from the given name), come only from choosing the pack
yourself: see :ref:`shipped-packs`.

Where you know a list's language, build the base with ``parser_for``
and call ``suggest()`` on that; the suggested parser keeps the pack.
Here the Spanish pack reads the two family names, and the list
supplies the order. A suggestion from the default parser gets the
order and not the second family name:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> spanish = parser_for(locales.ES)
    >>> padron = ["García López María", "Pérez Ruiz Juan", "Martínez Soto Ana"]
    >>> spanish.parse("García López María").family
    'López María'
    >>> spanish_list = spanish.suggest(padron)
    >>> spanish_list.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> spanish_list.parser.parse("García López María").family
    'García López'
    >>> Parser().suggest(padron).parser.parse("García López María").family
    'García'

Keeping the settings you applied
--------------------------------

A suggestion is one nameparser release's reading of a list, not a
fixed answer: the word tables and thresholds behind it are tuned
between releases, so a later release may suggest other settings for
the same names. Keep the settings you applied with your data
(``suggestion.patch``, or ``suggestion.parser.policy``, the ``Policy``
it made) and parse with those, rather than calling ``suggest()`` again
and expecting the same patch. Grouping keys are cut by one release the
same way (:ref:`matching-grouping-keys`).

A parser built from the kept ``Policy`` reads as the suggested one
did, and the kept patch, applied to the base's ``Policy``, gives the
same ``Policy`` back:

.. doctest::

    >>> kept = suggestion.parser.policy
    >>> kept
    Policy(name_order=FAMILY_FIRST)
    >>> Parser().parse("Taylor Morgan").given
    'Taylor'
    >>> Parser(policy=kept).parse("Taylor Morgan").given
    'Morgan'
    >>> Policy().patched(suggestion.patch) == kept
    True

Where the base was built with ``parser_for``, keep the pack as well:
copy that base with the kept ``Policy``. A kept patch goes onto that
base's ``Policy``, which holds the pack's settings, not onto a new
``Policy()``.

.. doctest::

    >>> import dataclasses
    >>> kept_spanish = dataclasses.replace(
    ...     spanish, policy=spanish_list.parser.policy)
    >>> kept_spanish.parse("García López María").family
    'García López'
    >>> spanish.policy.patched(spanish_list.patch) == kept_spanish.policy
    True
    >>> Policy().patched(spanish_list.patch) == kept_spanish.policy
    False

.. _suggest-limits:

Where it stops
--------------

A group is read right only once it carries enough names with evidence.
The figures below were measured on groups drawn from real names
written in a known order. They give a general idea of what to expect
and how it varies, and will differ for every dataset.

- **A list written in the base's own order** keeps it in at least 97%
  of groups from 2 to 200 names, save the two kinds of list below.
- **A list written the other way round** takes more names to move the
  base, from 5 for Chinese, Taiwanese, Korean, Czech, Polish and
  Italian names to 50 for Russian and Indian ones. A group whose votes
  fall short of the thresholds keeps the base rather than guess
  (:ref:`suggest-deciding`).

Two kinds of list keep their order less often:

- **Given names in capitals** (``ANNA Smith``) have their capitals read
  as a family name, and such a list is suggested ``capitals_as_family``
  too: nothing in a name tells it from a list that writes its family
  names in capitals, and its order is read the wrong way round already.
- **Two or three capitals at one end** cast no capitals vote
  (:ref:`suggest-evidence`), so a list of such names carries little
  evidence either way. Researchers' bylines written initials first kept a
  given-first base in at least 97% of groups, but a list of nothing
  but two or three joined initials (``AM Hoy``) kept it in just under
  95% of groups of 50. Where you know how such a list is written, set
  ``name_order`` yourself.

``capitals_as_family`` was suggested in at least 95% of groups from 4
names for researchers who typed their family name in capitals, and
from 10 for those in China, Korea, Vietnam and Taiwan, whose short
surnames are no evidence. Of the lists measured that do not write
their family names in capitals, only the one writing its given names
so was suggested it; no other was, the bylines (``AM Hoy``) included.

The parser never detects the language of a name; the suggester may,
over a group you declare, says what it saw, and its answer is
configuration you apply. The measurements, each with its date and its
exact figures, the thresholds and the evidence declined are in
``docs/design/decisions/group-suggestion.md``.
