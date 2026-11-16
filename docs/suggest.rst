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
source, one convention) and returns a :class:`~nameparser.Suggestion`.
Each name votes on its order from the evidence it carries
(:ref:`suggest-evidence`), and the group decides the order where enough
of its names agree (:ref:`suggest-deciding`). Three more settings are
decided the same way, each by its own evidence: a patronymic rule
(:ref:`suggest-patronymics`), ``initials_as_family``
(:ref:`suggest-initials`) and ``capitals_as_family``
(:ref:`suggest-capitals`). Every setting the votes do not decide keeps
the base parser's value.

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

Reading the result
------------------

``suggestion.parser`` is the base parser with ``suggestion.patch``
applied, so the base is never changed. ``suggestion.evidence`` holds a
:class:`~nameparser.SettingEvidence` for each setting considered and
``suggestion.names`` a :class:`~nameparser.NameEvidence` for each name,
in input order; ``print(suggestion)`` writes a report of each
setting's evidence and the names that disagree with it.
``disagreeing()`` lists the names whose vote is against a decided
setting, the ones to check by hand.

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
    >>> mixed.parser.parse("Emily Clark").given
    'Clark'

.. _suggest-evidence:

What a name votes on
--------------------

Each name votes on its order from the evidence it carries:

- **A family name written in capitals** at one end. A word of two or
  three capitals ending the name, or opening it with no word in
  capitals after it, is as often joined initials (``AM Hoy``) as a
  short surname (``NG Emily``), and casts no vote.
- **A trailing initial** (``Smith J.``), where at least three names,
  and 60% of the list's names that hold a name word, end in initials no
  other evidence in the same name contradicts, as a bibliography's do.
  Names with a comma, blanks and names of nothing but titles or marks
  leave the count. In a South Asian list the letters ending a name are
  often the family name, so a short list of bylines may get no order
  suggestion: where you know a list is bylines, set
  ``name_order=FAMILY_FIRST`` yourself.
- **A lowercase particle** first or before the last word.
- **A common romanized Chinese, Korean or Vietnamese surname** as the
  first or last word.
- **A common given name that is rarely a surname** (``Emily``, not
  ``Taylor``) as the first or last word.

Each is read past the titles and post-nominals your parser's vocabulary
lists (``Dr.``, ``PhD``, ``Jr.``). A name with a comma states its own
order and does not vote, unless only post-nominals follow the comma
(``Zhang Wei, PhD``), and neither does a name of one word.

The evidence need not be a surname. Here the common given names at the
end decide the order, and ``Ellis Jordan``, which carries none, follows
them:

.. doctest::

    >>> by_given = Parser().suggest(["Parker Emma", "Reed Sophie", "Ellis Jordan"])
    >>> by_given.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> by_given.parser.parse("Ellis Jordan").given
    'Jordan'

.. _suggest-deciding:

When the list decides the order
-------------------------------

The group decides ``name_order`` when at least two names vote for one
end and they are more than two thirds of the names that cast a vote.

Where no name in the list carries evidence, ``suggest()`` leaves every
setting as the base parser has it:

.. doctest::

    >>> Parser().suggest(["Taylor Morgan", "Jordan Casey", "Avery Quinn"]).patch
    PolicyPatch()

.. _suggest-patronymics:

Lists with patronymics
----------------------

A patronymic rule (East Slavic or Turkic,
:class:`~nameparser.PatronymicRule`) is decided only where at least
five names carry its patronymic and they are more than four in five of
the voting names, a name whose trailing initial alone was set aside
counting among them (the patronymic evidence's note says how many). A
patronymic votes only where the rule can read it (three name words for
East Slavic, three or four for Turkic).

A group decided East Slavic gets the rule and reads given-first, the
order that rule reorders each name under, unless its names' own votes
decide a family-first order, which the rule never overrides.

One case keeps a declared order instead: under a ``FAMILY_FIRST``
parser whose names' votes do not decide given-first, where more of the
names carrying the patronymic write it last (``Sidorov Ivan
Petrovich``) than in the middle (``Ivan Petrovich Sidorov``), the group
keeps that order and gets the rule alone, which reorders no name there
and fills the ``patronymic`` view; the names written the other way get
no given-first order, and the patronymic evidence's note counts them.
A tie, and a ``FAMILY_FIRST_GIVEN_LAST`` parser, get the given-first
order with the rule.

.. _suggest-initials:

Lists that end names in letters
-------------------------------

A list of South Asian names often ends each name in letters that are
the family name, and repeats them: Nepal's ``B K`` and ``K C`` are
surnames written short. Where one run of letters ends at least two of
the list's names and at least half of the names ending in letters,
``suggest()`` turns ``initials_as_family`` on (see
:ref:`initials-as-family`); its evidence is the ``initials_as_family``
entry of ``suggestion.evidence``, whose note names the letters. A list
whose letters are its family casts no trailing-initial vote on the
order. A base that reads names family first, or folds every middle name
into the family (``middle_as_family``), is suggested no change here:
the switch would change none of its names.

.. doctest::

    >>> nepal = Parser().suggest(["Durga B K", "Sita B.K.", "Hari Thapa"])
    >>> nepal.patch
    PolicyPatch(initials_as_family=True)
    >>> nepal.parser.parse("Ram Bahadur B K").family
    'B K'

.. _suggest-capitals:

Lists that write the family name in capitals
--------------------------------------------

Some lists write every family name in capitals (``Mary SMITH``), as
France's administrative style and several parliaments do. Where at
least two names, and more than two thirds of the names with evidence
either way, write their family in capitals, ``suggest()`` turns
``capitals_as_family`` on (see :ref:`capitals-as-family`), so the
capitals mark the family name wherever it stands. The order is decided
apart from it.

Each name counts for the switch, against it, or not at all:

- **For**: a name where the rule, asked of the name with the switch on,
  takes as its family a word in capitals of four letters or more that
  is no listed credential. A surname your vocabulary also lists as a
  title counts for it where your parser reads it as the family (``Mary
  BISHOP``), but not where it opens the name and your parser takes it
  for a title (``BISHOP Mary``).
- **Against**: a name of two words or more in mixed case with no word
  in capitals, which a name is once its titles and post-nominals are
  read past (``DR Ann Berg``, ``Prof. Ann Berg``, ``John Smith FRCS``);
  and a name where the switch would move the family onto a word your
  parser reads as a title in that name (``MISS Ann Berg``).
- **No evidence**: two or three capitals, being as often initials as a
  short surname (``AM Hoy``, ``Zhi LI``), and a name wholly in one
  case.

A group never turns the switch off, and a base reading an unlisted word
in capitals as a credential everywhere
(``unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE``) is suggested no
change, the two settings being opposite readings of the same word.

In the report, each setting counts its names for and against the value
the suggested parser has, so a list left with the switch off counts its
names in mixed case with no capitals as ``for`` (``6 for`` above), and
its names in capitals as ``against``; a name that writes no capitals
disagrees with a decided switch.

.. doctest::

    >>> capitals = Parser().suggest(["Mary SMITH", "Ruth HOLLIS", "Anna BERG"])
    >>> capitals.patch
    PolicyPatch(capitals_as_family=True)
    >>> Parser().parse("SMITH Mary").family
    'Mary'
    >>> capitals.parser.parse("SMITH Mary").family
    'SMITH'

.. _suggest-packs:

Choosing a language pack
------------------------

A suggestion never chooses a language pack. It proposes the four
``Policy`` settings above (``name_order``, ``patronymic_rules``,
``initials_as_family`` and ``capitals_as_family``) and leaves the
vocabulary as the base parser has it. The words a pack turns on, and
its other rules (two family names for Spanish, dividing a Chinese
surname from the given name), come only from choosing the pack
yourself: see :ref:`shipped-packs`. Where you know a list's language,
build the base with ``parser_for`` and call ``suggest()`` on that; the
suggested parser keeps the pack.

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

.. _suggest-limits:

Where it stops
--------------

A group is read right only once it carries enough names with evidence.
Measured on groups drawn from real names written in a known order, a
list written in the base's own order keeps it in at least 97% of groups
from 2 to 200 names, but moving the base takes more names, from 5 for
Chinese, Taiwanese, Korean, Czech, Polish and Italian names to 50 for
Russian and Indian ones.

Two kinds of list keep their order less often:

- **Given names in capitals** (``ANNA Smith``) have their capitals read
  as a family name.
- **Two or three capitals at one end.** A word of two or three capitals
  ending a name in mixed case, or opening it with no word in capitals
  after it (``DE SOUZA Maria`` still votes), is as often joined
  initials (``AM Hoy``, ``Armitage JO``) as a short surname (``NG
  Emily``, ``Zhi LI``), so it casts no capitals vote. A name opening in
  one casts no surname vote; the ending one casts no surname vote of
  its own, and where it is itself a listed surname (``Zhou NG``) the
  name casts none: its first word is usually the given name there, and
  the table cannot tell the two readings apart.

  ORCID's bylines written initials first kept a given-first base in at
  least 97% of groups, but a list of nothing but two or three joined
  initials (``AM Hoy``) kept it in just under 95% of groups of 50
  (94.7%). Lists of such names carry little evidence either way, so
  where you know how one is written, set ``name_order`` yourself.

``capitals_as_family`` was suggested in at least 95% of groups from 4
names for ORCID holders who typed their family name in capitals, and
from 10 for those in China, Korea, Vietnam and Taiwan, whose short
surnames are no evidence. Of the lists measured that do
not write their family names in capitals, only the one writing its
given names so was suggested it, which nothing in a name tells apart
and whose order is read the wrong way round already; no other was,
ORCID's bylines (``AM Hoy``) included.

A list whose names hold no such surname or given name (``Taylor
Morgan``, ``Jordan Casey``) carries no evidence, and a group whose
votes fall short of those thresholds keeps the base rather than guess.

The parser never detects the language of a name; the suggester may,
over a group you declare, says what it saw, and its answer is
configuration you apply. The measurements, each with its date, the
thresholds and the evidence declined are in
``docs/design/decisions/group-suggestion.md``, and
``tools/differential/suggest_measure.py`` re-takes them.
