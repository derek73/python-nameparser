.. _suggest-settings:

Settings for a list of names
============================

A list of names is usually written in one convention: a registry gives
every family name first, a mailing list every family name last. A
single name cannot show which, because ``Priem Jason`` and ``Jason
Priem`` are the same shape and only a reader who knows ``Priem`` is a
surname and ``Jason`` a given name can tell them apart. A whole list
can: most of its names carry some evidence, and the evidence agrees.

``Parser.suggest()`` reads a list you declare to be one group (one
source, one convention) and returns a :class:`~nameparser.Suggestion`.
Each name votes on its order from the evidence it carries: a family
name written in capitals at one end, a trailing initial
(``Smith J.``) where at least three names and 60% of the list end in
initials, as a bibliography's do (in a South Asian list the letters
ending a name are often the family name), a lowercase particle first
or before the last word, a
first or last word that is a common romanized Chinese, Korean or
Vietnamese surname, or a common given name, each read past the titles
and post-nominals your parser's vocabulary lists (``Dr.``, ``PhD``,
``Jr.``). A name with a comma states its own order and does not vote,
unless only post-nominals follow the comma (``Zhang Wei, PhD``), and
neither does a name of one word. The
group decides ``name_order`` when at least two names vote for one end
and they are more than two thirds of the names that cast a vote. A
patronymic rule (East Slavic or Turkic, :class:`~nameparser.PatronymicRule`) is
decided only where at least five names carry its patronymic and they
are more than four in five of the voting names, and a patronymic
votes only where the rule can read it (three name words for East
Slavic, four for Turkic); a group decided East Slavic reads
given-first, since that rule reorders each name itself and stands down
under a family-first order, unless its names' own votes decide a
family-first order, which the rule never overrides. Every setting the
votes do not decide keeps the base parser's value.

.. doctest::

    >>> from nameparser import Parser
    >>> listing = ["Priem Jason", "Kim Minjun", "Wang Xiaoming",
    ...            "Nguyen Anh", "Jason Priem"]
    >>> suggestion = Parser().suggest(listing)
    >>> suggestion.patch
    PolicyPatch(name_order=FAMILY_FIRST)
    >>> Parser().parse("Priem Jason").given
    'Priem'
    >>> suggestion.parser.parse("Priem Jason").given
    'Jason'
    >>> [entry.text for entry in suggestion.disagreeing()]
    ['Jason Priem']

``suggestion.parser`` is the base parser with ``suggestion.patch``
applied, so the base is never changed. ``suggestion.evidence`` holds a
:class:`~nameparser.SettingEvidence` for each setting considered and
``suggestion.names`` a :class:`~nameparser.NameEvidence` for each name,
in input order; ``print(suggestion)`` writes a report of each
setting's evidence and the names that disagree with it.
``disagreeing()`` lists the names whose vote is against a decided
setting, the ones to check by hand.

Where it stops. A group is read right only once it carries enough
names with evidence. Measured on groups drawn from real names written
in a known order (2026-11-10), a list written in the base's own order keeps it
in at least 98% of groups from 2 to 200 names, but moving the base
takes more names, from 5 for Chinese, Taiwanese, Korean, Czech and
Polish names to 200 for Indian ones. A plain list of names with no
common surname or given name in it (``Zxqv Brtk``) carries no evidence,
and a group whose votes fall short of those thresholds keeps the base
rather than guess. The
parser never detects the language of a name; the suggester may, over a
group you declare, says what it saw, and its answer is configuration
you apply. The measurements, the thresholds and the evidence declined
are in ``docs/design/decisions/group-suggestion.md``, and
``tools/differential/suggest_measure.py`` re-takes them.
