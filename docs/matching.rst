.. _matching-names:

Matching names across sources
=============================

``matches()`` asks whether two writings are the same name. Joining
records from several sources asks something looser: could these two
names belong to the same person? One source writes ``John A. Smith``,
another ``J. Smith``, a third ``JOHN SMITH JR.``. A name matcher
answers that question role by role, using the parse to know which
words are the family name, which are particles and which are initials,
and says *why* for every pair. It never scores a pair: combine its
answer with your own evidence (coauthors, institutions, identifiers)
and set your own thresholds.

The workflow is four steps:

#. Parse each source with its own :class:`~nameparser.Policy`, so two
   sources that write names in different orders each read correctly.
#. Build one :class:`~nameparser.Matching` from a parser with
   :meth:`Parser.matching() <nameparser.Parser.matching>`, and use it
   for both of the steps below.
#. Group the names by ``keys()``.
#. Within each group, ``check()`` each pair.

Grouping by key
---------------

``keys()`` gives each name a set of short strings, the family name's
words without their particles, and the whole family name joined (its
spaces and hyphens dropped, particles kept), each beside the given
name's first letter.
Two names ``check()`` calls consistent always share a key, so grouping
by key loses no match, and a pair that shares no key need never be
checked:

.. doctest::

    >>> from nameparser import Lexicon
    >>> from collections import defaultdict
    >>> from nameparser import Parser
    >>> matcher = Parser().matching()
    >>> sorted(matcher.keys("Jane A. de la Vega"))
    ['delavega;j', 'vega;j']
    >>> groups = defaultdict(list)
    >>> for written in ["John A. Smith", "J. Smith", "Juan de la Vega", "Juan Vega"]:
    ...     for key in matcher.keys(written):
    ...         groups[key].append(written)
    >>> dict(sorted(groups.items()))
    {'delavega;j': ['Juan de la Vega'], 'smith;j': ['John A. Smith', 'J. Smith'], 'vega;j': ['Juan de la Vega', 'Juan Vega']}

A family name of several words gets a key for each, because a source
may cut a surname list short, and a hyphenated one a key for each half,
for the two joined and for the whole word, save a half that is a
particle (``Al-Saud`` keys ``saud``, ``alsaud`` and ``al-saud``, never
``al``):

.. doctest::

    >>> sorted(matcher.keys("Mary Smith-Jones"))
    ['jones;m', 'smith-jones;m', 'smith;m', 'smithjones;m']

A key only gathers candidates: ``Jane Smith`` shares ``smith;j`` with
``John Smith``, and ``check()`` is what tells them apart. A name with
no family name, such as a lone ``Suharto`` (read as a given name, see
:ref:`lone-name-word`), gets no key and is consistent with nothing by
default, since the family name must be present on both sides and
agree; the search for other readings (below) reaches it through its
family reading.

Checking a pair
---------------

``check()`` takes two strings, parsed with the matcher's parser, or
two :class:`~nameparser.ParsedName` objects, compared as they were
parsed. It returns a :class:`~nameparser.MatchResult`: ``consistent``,
and in ``roles`` one :class:`~nameparser.RoleMatch` per field in field
order, each with its :class:`~nameparser.Outcome`, the text on each
side, and which :class:`~nameparser.Side` carried more of it. A row is
read by its field's name or :class:`~nameparser.Role`
(``result["family"]``), and ``weakest`` is the weakest row's outcome:

.. doctest::

    >>> smiths = matcher.check("John A. Smith", "J. Smith")
    >>> smiths.consistent
    True
    >>> for row in smiths.roles:
    ...     print(row.role.value, row.outcome.value, repr(row.left), repr(row.right), row.more.value)
    title same '' '' neither
    given initial 'John' 'J.' left
    middle one-side 'A.' '' left
    family same 'Smith' 'Smith' neither
    suffix same '' '' neither
    nickname same '' '' neither
    maiden same '' '' neither
    >>> smiths["given"].outcome.value, smiths.weakest.value
    ('initial', 'one-side')

**Consistent means nothing in the two names contradicts the match**,
under the outcomes accepted. It does not mean the two are the same
person: ``J. Smith`` is consistent with half the Smiths in a phone
book. The table is what lets you tell ``John A. Smith`` / ``John
Smith`` (only a middle initial missing) from ``J. Smith`` / ``John A.
Smith`` (most of the given name missing too), though both are
consistent. A pair is inconsistent when a role's outcome is
``conflict``, or one you have not accepted:

.. doctest::

    >>> johns = matcher.check("John Smith Jr.", "John Smith Sr.")
    >>> johns.consistent, johns["suffix"].outcome.value
    (False, 'conflict')

The check is symmetric: swapping the two names gives the same verdict
and the same table with ``left`` and ``right`` exchanged
(``MatchResult.mirrored()``). Each source keeps its own order, so
names parsed under different policies compare correctly:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Policy
    >>> family_first_source = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> matcher.check(family_first_source.parse("Smith John"), "John A. Smith").consistent
    True

What the default accepts
------------------------

The outcomes, in the order ``check()`` ranks them, strongest first.
``Outcome.strength`` gives that rank as an ordinal, larger for a
stronger outcome and 0 for ``conflict``; compare outcomes by it, since
``<`` on an :class:`~nameparser.Outcome` compares the names as strings
(``folded`` sorts before ``same``), but never store one: the values
change when an outcome is added. A row reports the strongest outcome
that holds and is accepted, and where none of those holding is
accepted, the strongest that holds, so an unaccepted one shows what
the pair needed. The default accepts the writing
variants a hand-built comparison usually forgives; the rest count as a
conflict until you accept them. ``familiar-form``, ``family-initial``,
``given-one-side`` and ``hyphenated-part`` are reported in the table
either way, so an unaccepted one shows what the pair needed. ``across-roles`` is
searched only where accepted, and each side's other readings only where
the search is switched on (below): otherwise the table shows the names
as parsed, and ``Suharto`` / ``Suharto`` reads family ``conflict``.

.. list-table::
   :header-rows: 1
   :widths: 22 38 12

   * - Outcome
     - Example (left / right)
     - Default
   * - ``same``
     - ``Smith`` / ``Smith``
     - yes
   * - ``folded``: equal once case, accents, full stops and apostrophes (typed or typographic) are folded away, and each hyphen the parser joins two names with (U+2010, the en dash and others) read as the hyphen-minus wherever the parser reads the name alike, which it does not for a credential joined by one (``MD‐PhD``)
     - ``María García`` / ``MARIA GARCIA``
     - yes
   * - ``joined``: equal once folded and stripped of spaces and hyphens, save where both are initials alone
     - ``Ignazio LaRussa`` / ``Ignazio La Russa``
     - yes
   * - ``listed-spelling``: spellings the vocabulary lists as one, in the role's own kind of word, a short form that is a name of its own too only written with its period
     - ``Wm. Smith`` / ``William Smith``
     - yes
   * - ``particles-aside``: the family names, or the maiden names, agree without their particles
     - ``Juan de la Vega`` / ``Juan Vega``
     - yes
   * - ``part-of-other``: one family or maiden name's words are among the other's, or listed spellings of them
     - ``Ana de Melo Schmitt`` / ``Ana de Melo Schmitt e Braga``
     - yes
   * - ``initial``: an initial against a name, outside the family name
     - ``J. Smith`` / ``John Smith``
     - yes
   * - ``initials-agree``: one role written in initials alone on both sides, the same initials once spaces and hyphens are set aside
     - ``Jane Doe (née J.-P.)`` / ``Jane Doe (née J. P.)``
     - yes
   * - ``one-side``: a middle name, nickname or maiden name on one side only
     - ``John A. Smith`` / ``John Smith``
     - yes
   * - ``generation-one-side``: a generation on one side only
     - ``John Smith`` / ``John Smith Jr.``
     - yes
   * - ``noted``: titles and credentials, which never conflict
     - ``Dr. John Smith`` / ``John Smith, PhD``
     - yes
   * - ``familiar-form``: two given names the vocabulary lists as a familiar-form pair, either way round, never chained
     - ``Bill Smith`` / ``William Smith``
     - no
   * - ``family-initial``: the family name written as an initial
     - ``John S.`` / ``John Stallbaum``
     - no
   * - ``given-one-side``: a given name on one side only
     - ``Mr. Smith`` / ``John Smith``
     - no
   * - ``hyphenated-part``: a given name against the first half of a hyphenated one
     - ``Hong Guo`` / ``Hong-Yi Guo``
     - no
   * - ``across-roles``: a name in a different role on each side
     - ``J. Edgar Hoover`` / ``Edgar Hoover``
     - no
   * - ``conflict``
     - ``John Smith`` / ``Jane Smith``
     - never

A listed spelling is read in the role's own kind of word: given names
for the given name, middle name and nickname, surnames and particles
for the family and maiden names, titles and suffixes for theirs. So
``Ma.`` (María written short) agrees with ``María`` as a given name,
while the surname Ma is another word, ``Ma, Jack`` / ``María, Jack``.
A short form that is also a name of its own, as ``Ma``, ``Jo`` (José)
and ``Jas`` (James) are, is read as its long form only written with
its period: ``Jo. Garcia`` / ``José Garcia`` agree, and ``Jo Garcia``
/ ``José Garcia`` conflict, the bare ``Jo`` being the name Jo, while
``Wm Smith`` and ``WM SMITH`` agree with ``William Smith``, ``Wm``
being no name of its own. It is read with accents folded too, so
``Jo. Garcia`` / ``Jose Garcia`` agree as ``Jo.`` / ``José`` do. A
listed spelling counts inside a family name word by word as it does
whole: with ``smyth`` added to a lexicon as a spelling of ``smith``,
``Ann de Smyth`` / ``Ann Smith`` read ``particles-aside`` and
``Ann Smyth-Jones`` / ``Ann Smith`` ``part-of-other``. A middle name
is compared word by word, in order, and takes the weakest of its
words' outcomes; where one side holds more words, the shorter side's
words need only agree, in order, with some of the longer side's, the
rest one-sided, so ``John Beth Smith`` / ``John Anne Beth Smith``
reads ``one-side``.
A different generation conflicts
(``Jr.`` / ``Sr.``), and a generation on one side only reads
``generation-one-side`` whatever credentials either side carries
(``John Smith Jr.`` / ``John Smith, PhD``); a credential or title
never conflicts, so a career from ``Mr.`` to ``Dr.`` does not separate
a person's records. The fold drops accents only from Latin, Greek and
Cyrillic letters; a mark on another script's letter, such as a
Devanagari vowel sign, is spelling and stays. Initials written joined
into one word agree with the same letters written apart as ``joined``
(``J.P. Smith`` / ``J.-P. Smith``). Typos (``Slvatore`` / ``Salvatore``) and
transliterations (``Igor`` / ``Ihor``) are conflicts. A familiar form
(``Peggy`` / ``Margaret``, below) you have not accepted keeps the pair
inconsistent though its row reads ``familiar-form``. The rows that kept a pair inconsistent are the
ones whose outcome you did not accept, and the table names their
roles, so you can run your own fuzzy comparison on those alone:

.. doctest::

    >>> peggy = matcher.check("Peggy Smith", "Margaret Smith")
    >>> [(r.role.value, r.outcome.value) for r in peggy.roles if r.outcome not in matcher.accept]
    [('given', 'familiar-form')]

Accepting more
--------------

``accept`` takes outcome names or :class:`~nameparser.Outcome`
members, and *replaces* the default set rather than adding to it, so
extend the default with the ``accept`` of a default matcher. The keys
follow what is accepted and the ``other_readings`` switch, so one
matcher's ``keys()`` and ``check()`` always agree; never group with one
matcher and check with another:

.. doctest::

    >>> with_family_initial = Parser().matching(accept=matcher.accept | {"family-initial"})
    >>> with_family_initial
    Matching(default + family-initial)
    >>> matcher.check("John S.", "John Stallbaum").consistent
    False
    >>> with_family_initial.check("John S.", "John Stallbaum").consistent
    True
    >>> sorted(with_family_initial.keys("John Stallbaum"))
    ['s;j', 'stallbaum;j']

A family initial is outside the default because its key, one letter of
the family name, gathers very large groups. An unknown outcome name
raises ``ValueError`` listing the valid ones, and ``conflict`` cannot
be accepted.

``other_readings=True``, a switch beside ``accept`` rather than an
outcome, tries each side's other reading where the names as parsed are
not consistent: one :ref:`ambiguity <parser-guesses>` at a time, its
words moved to the role its ``alternative`` names. Each row keeps its
own outcome under the other reading, so whatever else the pair needed
still shows, and ``left_alternative`` and ``right_alternative`` hold
the ambiguity whose other reading each side used, ``None`` for a side
read as parsed. A lone ``Suharto``, read as a given name, has the
family reading as its alternative:

.. doctest::

    >>> with_other_reading = Parser().matching(other_readings=True)
    >>> with_other_reading
    Matching(default + other-readings)
    >>> lone = with_other_reading.check("Suharto", "Suharto")
    >>> lone.consistent, lone["family"].outcome.value
    (True, 'same')
    >>> lone.left_alternative.kind.value, lone.left_alternative.alternative.role.value
    ('given-or-family', 'family')
    >>> sorted(with_other_reading.keys("Suharto"))
    ['suharto;']

An alternative that would move words into the title or the suffix is
not tried, so a given name cannot vanish into one of them to agree
with another.

``familiar-form`` reads a short given name as standing for the longer
ones the vocabulary lists it under: ``Max`` for Maximilian and
Maxwell, ``Bill`` for William, ``Peggy`` for Margaret. It is read in the
given name, middle name and nickname, never the family name. A pair
is read whichever way the vocabulary wrote it, since its sources do
not always write the shorter name first (``Barbara`` / ``Babs``), but
never chained, so two longer names paired with one short name do not
agree with each other. The keys follow: a name is keyed by the first
letters of the names it is paired with too, so ``Bill Smith`` meets
``William Smith`` in a group:

.. doctest::

    >>> with_familiar = Parser().matching(accept=matcher.accept | {"familiar-form"})
    >>> bill = with_familiar.check("Bill Smith", "William Smith")
    >>> bill.consistent, bill["given"].outcome.value
    (True, 'familiar-form')
    >>> matcher.check("Bill Smith", "William Smith")["given"].outcome.value
    'familiar-form'
    >>> with_familiar.check("Maximilian Smith", "Maxwell Smith").consistent
    False
    >>> sorted(with_familiar.keys("Bill Smith"))
    ['smith;b', 'smith;w']

The shipped familiar forms, 2,845 pairs (counted 2026-11-12), come
from two sources. Old Dominion University's nicknames list (Apache
License 2.0), a lookup of English given names' nicknames and
diminutives (``Ricky`` / ``Richard``, ``Peggy`` / ``Margaret``), is in
the English file, less the pairs a review refused as another
language's form (``Ivan`` / ``John``), another name (``Erin`` /
``Aaron``) or two forms of one name neither made from the other
(``Lisa`` / ``Liz``). The rest, in many languages (``Kasia`` /
``Katarzyna``, ``Kostas`` / ``Konstantinos``, ``Seun`` /
``Oluwaseun``), are pairs ORCID's researchers wrote for themselves both
ways, in the given-name box and in a published name, each read by two
reviewers, in the file of the languages written where their holders
work. The same review gives the given names' listed spellings
(``Łukasz`` / ``Lukasz``, ``Aleksey`` / ``Alexey``, ``Saeed`` /
``Saeid``), which read ``listed-spelling`` and so are accepted by
default. A plain choice of languages keeps every file's pairs, and a
strict one keeps its own files' and the shared ones. A pair whose short name
reads as a title in front of a name (``Ab``, ``Nanny``) is never
compared as a given name, so it stays inert while the title reading
stands. It is a selection and has gaps (``Rickie`` /
``Richard`` and ``Sepp`` / ``Josef`` are not in it); add your own with a
``familiar`` reading,
which extends the names the word's shipped readings list (to replace
them, ``remove(word, kind="familiar")`` first):

.. doctest::

    >>> rickie = Lexicon.default().add("rickie", kind="familiar", short_for=["richard"])
    >>> mine = Parser(lexicon=rickie).matching(accept=matcher.accept | {"familiar-form"})
    >>> mine.check("Rickie Smith", "Richard Smith").consistent, mine.check("Rickie Smith", "Roderick Smith").consistent
    (True, True)

A familiar form is outside the default because it is many-valued and
often a name of its own: ``Max`` is a given name in its own right, as
``Bill`` and ``Peggy`` are.

``across-roles`` compares a given name with each word of the other
name's middle name and with its nickname, and a family name with the
other's maiden name. It counts only a full name on both sides, never
an initial, and records each match it made in ``across``:

.. doctest::

    >>> with_across = Parser().matching(accept=matcher.accept | {"across-roles"})
    >>> hoover = with_across.check("J. Edgar Hoover", "Edgar Hoover")
    >>> hoover.consistent, hoover["given"].outcome.value
    (True, 'across-roles')
    >>> hoover.across[0].left_role.value, hoover.across[0].right_role.value, hoover.across[0].left
    ('middle', 'given', 'Edgar')
    >>> with_across.check("Jane Doe (née Smith)", "Jane Smith").consistent
    True

The middle word a match uses is taken out of the middle comparison,
and the middle words left are compared role to role.

.. _matching-without-an-inherited-family-name:

Names with no inherited family name
-----------------------------------

Some conventions have no inherited family name. An Ethiopian or
Eritrean name is the person's own name, then the father's, then often
the grandfather's, and where only two are written abroad the father's
name is filed as the surname. The parser reads by position, so the
father's name is the ``family`` of ``Dawit Bekele`` and the ``middle``
of ``Dawit Bekele Tesfaye``, whose family is the grandfather's. The
default matcher therefore keeps the two spellings of one person apart:

.. doctest::

    >>> matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele")["family"].outcome.value
    'conflict'

For a list known to follow this convention, build the matcher from a
parser that folds the middle names into the family
(``middle_as_family``). The father's name is then part of the family on
both sides, so the two spellings are consistent and share a key, while a
different father, or a different grandfather behind the same father,
still conflicts:

.. doctest::

    >>> from nameparser import Policy
    >>> ethiopian_matcher = Parser(policy=Policy(middle_as_family=True)).matching()
    >>> dawit = ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele")
    >>> dawit.consistent, dawit["family"].outcome.value
    (True, 'part-of-other')
    >>> sorted(ethiopian_matcher.keys("Dawit Bekele Tesfaye")
    ...        & ethiopian_matcher.keys("Dawit Bekele"))
    ['bekele;d']
    >>> ethiopian_matcher.check("Dawit Bekele", "Dawit Tesfaye").consistent
    False
    >>> ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Bekele Haile").consistent
    False

Keep the default parser for reading the fields: the fold reads the
grandfather's name into the family too, and on ORCID's Ethiopian
records, where holders filed their own names, it agrees with their
boxes about 21.5 points less often than the default does (measured
2026-11-12, #1203).

The matcher compares a family of several words regardless of order, and
the fold makes every such family several words, so two names consistent
under it are not always one person. A name whose father and grandfather
are written the other way round is consistent, and so, under either
matcher, is a two-word name whose second word is the other name's
grandfather:

.. doctest::

    >>> ethiopian_matcher.check("Dawit Bekele Tesfaye", "Dawit Tesfaye Bekele").consistent
    True
    >>> matcher.check("Dawit Bekele Tesfaye", "Dawit Tesfaye").consistent
    True

And use it only for such a list: it treats every middle name as part of
the family, so it also calls ``John Paul Smith`` and ``John Paul``
consistent, which the default matcher keeps apart:

.. doctest::

    >>> ethiopian_matcher.check("John Paul Smith", "John Paul").consistent
    True
    >>> matcher.check("John Paul Smith", "John Paul").consistent
    False

The fold has a cost the other way too. A father's name written as an
initial becomes part of the family, so the pair conflicts as a family
written with an initial (``family-initial``, which the default does not
accept), where the default matcher reads a middle initial and calls it
consistent. Accept ``family-initial`` on the folded matcher to restore
it:

.. doctest::

    >>> matcher.check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye").consistent
    True
    >>> ethiopian_matcher.check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye")["family"].outcome.value
    'family-initial'
    >>> Parser(policy=Policy(middle_as_family=True)).matching(
    ...     accept=ethiopian_matcher.accept | {"family-initial"}
    ... ).check("Dawit B. Tesfaye", "Dawit Bekele Tesfaye").consistent
    True

Neither matcher removes a title the vocabulary does not list: ``Ato``
reads as the given name, so ``Ato Dawit Bekele Tesfaye`` and
``Dawit Bekele`` conflict under both.

Consistency is not transitive
-----------------------------

``J. Smith`` is consistent with ``John Smith`` and with ``Jane
Smith``, which are not consistent with each other:

.. doctest::

    >>> matcher.check("J. Smith", "John Smith").consistent
    True
    >>> matcher.check("J. Smith", "Jane Smith").consistent
    True
    >>> matcher.check("John Smith", "Jane Smith").consistent
    False

So do not merge records by chaining consistent pairs: a less specific
name joins people a more specific one keeps apart. ``RoleMatch.more``
tells you which side carried more of each role, so of a consistent
pair, one name is a less specific writing of the other when no role
has it carrying more:

.. doctest::

    >>> def less_specific(result):
    ...     return all(row.more.value != "left" for row in result.roles)
    >>> less_specific(matcher.check("J. Smith", "John A. Smith"))
    True
    >>> less_specific(matcher.check("John A. Smith", "J. Smith"))
    False

A role read ``across-roles`` has the side carrying more that held both
the role and the role it was matched against, so ``J. Edgar Hoover``,
which holds a given initial beside the middle name the other uses as
its given name, is the more specific of the two:

.. doctest::

    >>> less_specific(with_across.check("Edgar Hoover", "J. Edgar Hoover"))
    True
    >>> less_specific(with_across.check("J. Edgar Hoover", "Edgar Hoover"))
    False

Link each record to its most specific consistent name rather than to
every name it is consistent with.
