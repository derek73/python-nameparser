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
Each name votes on its order from the evidence it carries: a family
name written in capitals at one end, a trailing initial
(``Smith J.``) where at least three names, and 60% of the list's names
that hold a name word (names with a comma, blanks and names of nothing
but titles or marks leave the count), end in initials no other evidence
in the same name contradicts, as a bibliography's do (in a South Asian
list the letters ending a name are often the family name; a short list
of bylines may therefore get no order suggestion, so where you know a
list is bylines, set ``name_order=FAMILY_FIRST`` yourself), a lowercase
particle first
or before the last word, a
first or last word that is a common romanized Chinese, Korean or
Vietnamese surname, or a common given name that is rarely a surname
(``Emily``, not ``Taylor``), each read past the titles
and post-nominals your parser's vocabulary lists (``Dr.``, ``PhD``,
``Jr.``). A name with a comma states its own order and does not vote,
unless only post-nominals follow the comma (``Zhang Wei, PhD``), and
neither does a name of one word. The
group decides ``name_order`` when at least two names vote for one end
and they are more than two thirds of the names that cast a vote. A
patronymic rule (East Slavic or Turkic, :class:`~nameparser.PatronymicRule`) is
decided only where at least five names carry its patronymic and they
are more than four in five of the voting names, a name whose trailing
initial alone was set aside counting among them (the patronymic
evidence's note says how many), and a patronymic
votes only where the rule can read it (three name words for East
Slavic, three or four for Turkic); a group decided East Slavic reads
given-first, since that rule reorders each name itself and stands down
under a family-first order, unless its names' own votes decide a
family-first order, which the rule never overrides. Every setting the
votes do not decide keeps the base parser's value.

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
name at the end. ``Taylor Morgan`` gives no evidence: it is read family
first because the list is, and nothing in the name can confirm that.

.. _suggest-disagreeing:

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
          given-name FAMILY_FIRST  1
          given-name GIVEN_FIRST  1
      patronymic_rules  unchanged (none)  no evidence
      initials_as_family  unchanged (False)  no evidence
      disagreeing (1): Emily Clark
    >>> mixed.parser.parse("Emily Clark").given
    'Clark'

The evidence need not be a surname. Here the common given names at the
end decide the order, and ``Ellis Jordan``, which carries none, follows
them:

.. doctest::

    >>> by_given = Parser().suggest(["Parker Emma", "Reed Sophie", "Ellis Jordan"])
    >>> by_given.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> by_given.parser.parse("Ellis Jordan").given
    'Jordan'

Where no name in the list carries evidence, ``suggest()`` leaves every
setting as the base parser has it:

.. doctest::

    >>> Parser().suggest(["Taylor Morgan", "Jordan Casey", "Avery Quinn"]).patch
    PolicyPatch()

``suggestion.parser`` is the base parser with ``suggestion.patch``
applied, so the base is never changed. ``suggestion.evidence`` holds a
:class:`~nameparser.SettingEvidence` for each setting considered and
``suggestion.names`` a :class:`~nameparser.NameEvidence` for each name,
in input order; ``print(suggestion)`` writes a report of each
setting's evidence and the names that disagree with it.
``disagreeing()`` lists the names whose vote is against a decided
setting, the ones to check by hand.

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

Where it stops. A group is read right only once it carries enough
names with evidence. Measured on groups drawn from real names written
in a known order (2026-11-10, re-taken 2026-11-11), a list written in the base's own order keeps it
in at least 98% of groups from 2 to 200 names, but moving the base
takes more names, from 5 for Chinese, Taiwanese, Korean, Czech and
Polish names to 200 for Indian ones. One list keeps its order less
often: bylines written with the initials first (``GH Yoon``), whose
joined initials are read as a family name, so a group of ten or more is
usually suggested family-first. A list whose names hold no such surname or
given name (``Taylor Morgan``, ``Jordan Casey``) carries no evidence,
and a group whose votes fall short of those thresholds keeps the base
rather than guess. The
parser never detects the language of a name; the suggester may, over a
group you declare, says what it saw, and its answer is configuration
you apply. The measurements, the thresholds and the evidence declined
are in ``docs/design/decisions/group-suggestion.md``, and
``tools/differential/suggest_measure.py`` re-takes them.
