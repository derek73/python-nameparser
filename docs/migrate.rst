Migrating to 3.0
================

nameparser 3.0 removes the 1.x compatibility layer: ``HumanName``,
``Constants`` and everything around them, which 2.x kept working on top
of the core parser and 2.8 deprecated. This page is for code moving to
3.0, 3.1 or 3.2 from 1.x or from any 2.x release, whether it called
``HumanName`` or the 2.x core API. It says what is gone and what
replaces each piece, one row per old name, and lists the names whose
reading changed, release by release.

The 3.0 API is the one 2.0 introduced — ``parse``, ``Parser``,
``Lexicon``, ``Policy``, ``Locale`` and ``ParsedName``, with
:mod:`nameparser.locales` — and its names and signatures carry into 3.0
gaining additions only, save one: a ``Lexicon`` is configured by
*reading* in 3.0, its 2.x set fields internal, and the modules in
``nameparser.config`` that exposed the default word lists as constants
(``titles``, ``particles`` and the rest) are gone, a lexicon listing its
words instead. Separately, the output model changes in 3.0: ``str()``
now renders a name in the order it was read in, with the separators it
was written with.

The full 1.x documentation remains the reference for ``HumanName`` and
stays online as the 1.4.0 build on readthedocs:
https://nameparser.readthedocs.io/en/v1.4.0/

Which part is yours
-------------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Your code
     - Read
   * - calls ``HumanName``
     - :ref:`migrate-removed`, then the :ref:`migrate-attribute-map`
   * - was written against 1.x
     - :ref:`migrate-earlier-breaks` as well: what 2.0 removed still
       applies
   * - edits ``CONSTANTS`` or builds a ``Constants``
     - the :ref:`migrate-config-map`
   * - uses the 2.x ``Lexicon`` and ``Policy`` and is going to 3.0,
       3.1 or 3.2
     - :ref:`migrate-lexicon-readings`, :ref:`migrate-constants`,
       :ref:`migrate-3-0`, :ref:`migrate-3-1` and :ref:`migrate-3-2`;
       the attribute map and the ``Constants`` tables are not yours
   * - compares names with ``==``
     - :ref:`migrate-comparison`
   * - pickles parsers, lexicons or parsed names
     - :ref:`migrate-pickles`
   * - has tests whose expected readings changed after upgrading
     - :ref:`migrate-behavior`, which lists the changes release by
       release

Upgrade steps
-------------

1. Upgrade to 2.8.2, which warns of most of what 3.0 removes
   (:ref:`migrate-removed`).
2. Run your tests with deprecation warnings turned into errors
   (:ref:`migrate-finding-sites`). The run stops at each use 3.0
   removes, except the ones 2.8.2 does not warn on.
3. Search your code for those: the ``grep`` under
   :ref:`migrate-finding-sites` finds the names, and a read of a
   ``Lexicon`` set field has to be found by hand.
4. If you keep pickles, read :ref:`migrate-pickles` before leaving 3.0
   behind: a ``Lexicon``, ``Parser`` or locale pack pickled by 2.7 or
   2.8 loads under 3.0 and not under 3.1, so pickle it again under 3.0.
   That load raises a ``DeprecationWarning``, so it stops a run that
   turns warnings into errors.
5. Upgrade, and compare your fixtures with the lists under
   :ref:`migrate-behavior` for the releases between your old version
   and the new one.

.. _migrate-removed:

What 3.0 removes
----------------

2.8 warned at the line in your code that used each of these, 2.8.1
where code reads a constant of ``nameparser.config.regexes`` or a
vocabulary module, and 2.8.2 where it
reads ``KOREAN_SURNAMES``, with the exceptions :ref:`migrate-finding-sites`
names:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Removed
     - Replacement
   * - ``HumanName(...)``, and the ``nameparser.parser`` module
     - ``nameparser.parse(text)``, or ``Parser(lexicon=...,
       policy=...).parse(text)``; the fields are ``given`` and
       ``family`` where ``HumanName`` has ``first`` and ``last``. See
       the :ref:`migrate-attribute-map`
   * - ``Constants(...)``, ``constants.copy()`` and the shared
       ``CONSTANTS``
     - ``Parser(lexicon=Lexicon.default().remove("dean",
       kind="given"))``, and the :ref:`migrate-config-map` for each
       setting
   * - ``SetManager``, ``TupleManager`` and ``RegexTupleManager`` in
       ``nameparser.config``
     - ``Lexicon.add`` and ``Lexicon.remove`` take words and a reading
       kind: ``Lexicon.default().add("leed", kind="credential")``
   * - ``nameparser.util`` and its ``lc``
     - ``value.lower().strip(".")``
   * - Loading a pickled ``HumanName``
     - Store ``parse(text).as_dict()`` or the original string
       (:ref:`migrate-pickles`)
   * - Loading a pickled ``Constants``
     - Pickle the ``Parser`` instead (:ref:`migrate-pickles`)
   * - The 1.x names of five word lists and two of their modules,
       deprecated since 2.2
     - None in 3.0: their 2.2 names, which the 2.2.0 entry of
       :doc:`release_log` maps, went with the vocabulary modules (next
       row)
   * - The vocabulary modules ``nameparser.config.titles``,
       ``suffixes``, ``particles``, ``conjunctions``,
       ``bound_given_names``, ``given_names``, ``maiden_markers`` and
       ``capitalization``, which 2.8.1 warns of
     - ``Lexicon.default().words(kind=...)``, the call or comprehension
       for each constant in :ref:`migrate-constants`
   * - ``nameparser.config.surnames`` and its ``KOREAN_SURNAMES``, which
       2.8.2 warns of
     - ``Lexicon.default().surnames``, which holds the same words
   * - ``nameparser.config.regexes`` and its ``REGEXES``, which the
       parser has not read since 2.0
     - Copy the pattern you reused into your own code; the bidi and
       emoji strip switches moved to ``Policy``
       (:ref:`migrate-policy-settings`)

The 2.8 deprecation warnings go with the code they warned about. In 3.0
importing a removed name raises ``ImportError``, reading one as an
attribute raises ``AttributeError``, and a pickle of a ``HumanName`` or
a ``Constants`` cannot load, because there is no class to load it into.

.. _migrate-finding-sites:

Finding the sites
~~~~~~~~~~~~~~~~~

Upgrade to 2.8.2 first. A ``DeprecationWarning`` is hidden by default
outside ``__main__``, so run your tests with warnings turned into
errors, and each use 3.0 removes stops the run at the line that makes
it:

.. code-block:: bash

    python -W error::DeprecationWarning -m pytest

2.8 warns where code *uses* a removed name, not where it imports one,
2.8.1 warns where code reads a constant of a removed module,
``nameparser.config.regexes`` or a vocabulary module
(``from nameparser.config.titles import TITLES`` included), not where it
imports the module, and 2.8.2 the same for
``nameparser.config.surnames``, so some code passes that check and
still fails on 3.0:

* *reading* the shared ``CONSTANTS`` (``"dr" in CONSTANTS.titles``, or
  ``copy.copy(CONSTANTS)``), which 2.8 left quiet so that importing
  ``nameparser`` stays quiet
* an import whose name the code never uses, or uses without
  constructing it — ``from nameparser import HumanName`` or ``from
  nameparser.config import Constants`` behind a subclass, an
  ``isinstance`` check or an annotation; ``import nameparser.util``;
  importing ``nameparser.parser`` or the two 1.x word-list modules,
  ``nameparser.config.prefixes`` and
  ``nameparser.config.bound_first_names``
* importing ``nameparser.config.regexes``, ``nameparser.config.surnames``
  or a vocabulary module without reading a constant from it — ``import
  nameparser.config.regexes``, ``import nameparser.config.titles`` or
  ``from nameparser.config import particles``
* *reading* a ``Lexicon`` set field (``"dr" in lexicon.titles``), which
  2.8.1 warns of only where code writes one, and which raises
  ``AttributeError`` in 3.0 (:ref:`migrate-lexicon-readings`)

So search your code for those names as well: the shared ``CONSTANTS``,
``HumanName`` and ``Constants``, the ``nameparser.parser`` and
``nameparser.util`` modules, any import from ``nameparser.config``, and
the removed modules of that package by name:

.. code-block:: bash

    grep -rnE "CONSTANTS|HumanName|Constants|nameparser\.(parser|util)\b|nameparser\.config import|config\.(prefixes|bound_first_names|regexes|surnames|titles|suffixes|particles|conjunctions|bound_given_names|given_names|maiden_markers|capitalization)" .

A read of a ``Lexicon`` set field has no name to search for: look where
your code holds a lexicon.

.. _migrate-earlier-breaks:

Earlier breaks 3.0 keeps
------------------------

Neither list below is a 3.0 removal: each break arrived in a 2.x
release, and 3.0 keeps it.

Coming from 1.x
~~~~~~~~~~~~~~~

Code written against 1.4 meets 2.0's removals too, since 3.0 keeps
them. Most are moot now that ``HumanName`` and ``Constants`` are gone,
but three still reach code moving to ``parse()``:

* ``name == "John Smith"`` returned ``True`` on 1.x, and a
  ``ParsedName`` compared to a string is never equal to it: use
  ``matches()`` (:ref:`migrate-comparison`)
* bytes are not decoded for you: ``parse(b"...")`` raises
  ``TypeError``, so decode first (``raw.decode("utf-8")``)
* ``CONSTANTS.regexes.bidi = False``, 1.3.1's opt-out for keeping
  bidirectional marks, and the emoji one are ``Policy`` fields
  (:ref:`migrate-policy-settings`)

Breaks in the 2.x core API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Later 2.x releases changed the core API in ways 3.0 keeps:

* editing a default word list in place — ``TITLES.add("dean")`` —
  raises ``AttributeError`` since 2.2, when the vocabulary sets became
  ``frozenset``; 3.0 removes those constants' modules
  (:ref:`migrate-constants`)
* a ``capitalization_exceptions`` value that is not a case mask of its
  key — ``{"md": "Doc"}`` — raises ``ValueError`` since 2.4
* a pickle written by an earlier 2.x release raises ``ValueError`` on
  load since 2.6 or 2.7, by the object (:ref:`migrate-pickles`)

.. _migrate-attribute-map:

Attribute map
-------------

``HumanName``'s seven fields and their aggregates map onto
:class:`~nameparser.ParsedName`, which :func:`~nameparser.parse`
returns, like this:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - 1.x/2.x ``HumanName``
     - 3.0 ``ParsedName``
     - Note
   * - ``title``
     - ``title``
     -
   * - ``first``
     - ``given``
     -
   * - ``middle``
     - ``middle``
     -
   * - ``last``
     - ``family``
     -
   * - ``suffix``
     - ``suffix``
     -
   * - ``nickname``
     - ``nickname``
     -
   * - ``maiden``
     - ``maiden``
     - New field (added 1.3)
   * - ``title_list``, ``first_list``, ``middle_list``, ``last_list``,
       ``suffix_list``, ``nickname_list``, ``maiden_list``
     - ``tokens_for(Role.TITLE)``, ``tokens_for(Role.GIVEN)``, ...
     - Returns the raw :class:`~nameparser.Token` tuple for that role;
       read ``.text`` off each token for the string a ``_list``
       attribute gave you
   * - ``given_names`` / ``given_names_list``
     - ``given_names``
     - Unchanged name; ``middle`` folded into ``given``
   * - ``surnames`` / ``surnames_list``
     - ``surnames``
     - Unchanged name; ``middle`` folded into ``family``
   * - ``last_base`` / ``last_base_list``
     - ``family_base``
     - The surname without its particles, every one of them: for
       ``da Silva do Amaral``, ``"Silva Amaral"``, where ``HumanName``
       split off only the leading ones (``"Silva do Amaral"``)
   * - ``last_prefixes`` / ``last_prefixes_list``
     - ``family_particles``
     - The particles ``family_base`` was split from (e.g. ``"de la"``),
       a particle inside the surname included: ``"da do"`` for
       ``da Silva do Amaral``, where ``HumanName`` gave ``"da"``
   * - ``string_format``
     - ``render(spec)``
     - A per-call argument now, not stored config — see
       :ref:`rendering-arguments`
   * - ``initials()``
     - ``initials()``
     - The same reading, except that ``HumanName`` initialed a joined
       element such as ``Ph. D.`` as one: ``"Ph. D., John"`` gave
       ``J. P D.`` there and gives ``J. P. D.`` here, as on 1.4
   * - ``initials_list()``
     - none
     - ``ParsedName`` has no list view of the initials;
       ``initials(spec)`` renders the ones you need
   * - ``initials_format``, ``initials_delimiter``, ``initials_separator``
     - ``initials(spec, delimiter, separator)``
     - Same three knobs, now call-site arguments to
       :meth:`~nameparser.ParsedName.initials` — see
       :ref:`rendering-arguments`
   * - ``suffix_delimiter``
     - ``Policy(extra_suffix_delimiters=frozenset({...}))``
     - Now a ``Policy`` set field, so several delimiters can be
       active (:ref:`suffix-delimiters`)
   * - ``capitalize(force=...)``
     - ``capitalized(force=...)``
     - :meth:`~nameparser.ParsedName.capitalized` returns a new value
       rather than mutating in place. Its optional first argument takes
       a :class:`~nameparser.Lexicon`, if you need custom
       capitalization exceptions
   * - ``full_name``, ``original``
     - ``original``
     - The text as passed in
   * - ``name["first"]``, ``as_dict()``
     - ``as_dict()["given"]``
     - The keys are the 3.0 field names
   * - ``iter(name)``, ``len(name)``
     - ``[v for v in name.as_dict().values() if v]``
     - The non-empty fields, in field order
   * - ``name.first = "Jane"``
     - ``Parser().revise(name, given="Jane")``
     - Returns a new value, the replacement read by the parser;
       ``name.replace(given="Jane")`` splices the text in unread
   * - ``HumanName(first="Juan", last="de la Vega")``
     - ``Parser().revise(parse(""), given="Juan", family="de la Vega")``
     - Builds a name from its fields
   * - ``C``, ``has_own_config``, ``parse_full_name()``
     - none
     - A ``ParsedName`` holds no config. The ``Parser`` that read it
       does; to read the name again with other config, call
       ``parser.parse(name.original)``
   * - ``collapse_whitespace()``
     - none
     - ``parse()`` collapses whitespace itself

``suffix_delimiter`` moved as a *set*, not just under a new name:
passing the old scalar through (``extra_suffix_delimiters=" - "``)
raises, rather than silently registering three one-character
delimiters.

Side by side, the 1.x and 2.x spelling:

.. code-block:: python

    hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
    hn.title, hn.first, hn.last         # ('Dr.', 'Juan', 'de la Vega')
    hn.first_list                       # ['Juan']
    hn.last_base, hn.last_prefixes      # ('Vega', 'de la')

and the 3.0 one, reading the same name:

.. doctest::

    >>> from nameparser import parse, Role
    >>> n = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> n.title, n.given, n.family
    ('Dr.', 'Juan', 'de la Vega')
    >>> [t.text for t in n.tokens_for(Role.GIVEN)]
    ['Juan']
    >>> n.given_names, n.surnames
    ('Juan Q. Xavier', 'Q. Xavier de la Vega')
    >>> n.family_base, n.family_particles
    ('Vega', 'de la')

Editing a field, and building a name from fields:

.. doctest::

    >>> from nameparser import Parser
    >>> Parser().revise(n, given="Jane").given
    'Jane'
    >>> built = Parser().revise(parse(""), given="Juan", family="de la Vega")
    >>> built.family, built.family_particles
    ('de la Vega', 'de la')

.. _migrate-config-map:

Config map
----------

Vocabulary sets → Lexicon
~~~~~~~~~~~~~~~~~~~~~~~~~

The vocabulary sets of a 1.x or 2.x ``Constants`` (and so of the shared
``CONSTANTS``) map onto the 2.x :class:`~nameparser.Lexicon` field of
the second column, and each of those onto the readings of
:ref:`migrate-lexicon-readings` below:

.. list-table::
   :header-rows: 1
   :widths: 34 33 33

   * - 1.x/2.x ``Constants``
     - 2.x ``Lexicon`` field
     - Note
   * - ``titles``
     - ``titles``
     -
   * - ``first_name_titles``
     - ``given_name_titles``
     -
   * - ``suffix_acronyms``
     - ``suffix_acronyms``
     -
   * - ``suffix_not_acronyms``
     - ``suffix_words``
     -
   * - ``suffix_acronyms_ambiguous``
     - ``suffix_acronyms_ambiguous``
     -
   * - ``prefixes``
     - ``particles``
     -
   * - ``non_first_name_prefixes``
     - ``particles_ambiguous``
     - **Flipped** — see the warning below
   * - ``conjunctions``
     - ``conjunctions``
     -
   * - ``bound_first_names``
     - ``bound_given_names``
     -
   * - ``capitalization_exceptions``
     - ``capitalization_exceptions``
     - A field still. Pair-valued, so not ``add()``/``remove()``; extend
       the defaults with ``dataclasses.replace()`` as
       :ref:`case-exceptions` shows. Since 2.4 a value is a case mask,
       so ``{"md": "M.D."}`` repairs ``md`` to ``MD``

.. warning::

   ``non_first_name_prefixes`` lists particles that are *never* read as
   a given name, which 3.0 spells as a particle with no ``given``
   reading; a particle that *may* be read as one holds a ``given``
   reading too. 2.x's constant ``particles.NON_GIVEN_NAME_PARTICLES``
   marked the never-given set, however much its name suggests
   otherwise. So a 1.x ``non_first_name_prefixes`` entry is
   ``remove(word, kind="given")``, and a word missing from it
   ``add(word, kind="given")``.

.. _migrate-lexicon-readings:

Lexicon fields → readings
~~~~~~~~~~~~~~~~~~~~~~~~~

A 3.0 :class:`~nameparser.Lexicon` holds readings, what a word may be
read as in the vocabulary files' terms, and compiles the sets a parse
reads from them; the 2.x set fields are internal. A caller states what
a word is, and the lexicon derives which sets that puts it in, so
making ``Guru`` a possible given name is ``add("guru", kind="given")``
where 2.x needed ``remove(titles={"guru"}).add(titles_ambiguous={"guru"})``.
Each 2.x spelling raises where it is written:

- ``add(...)`` or ``remove(...)`` with a set field as a keyword raises
  ``TypeError`` naming the field and pointing at the table below, which
  gives the kind each field's words take;
- ``Lexicon(titles=...)`` and ``dataclasses.replace(lexicon,
  titles=...)`` raise the same way;
- reading ``lexicon.titles`` raises ``AttributeError``, naming
  :meth:`~nameparser.Lexicon.readings_of`, and for what a parse read,
  :attr:`Token.reading <nameparser.Token.reading>`.

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - 2.x ``Lexicon`` field
     - 3.0 reading
   * - ``titles``
     - ``add(w, kind="title")``, or a finer title kind (``office``,
       ``academic``, ...); where the word holds a ``given`` reading,
       ``remove(w, kind="given")`` makes it a title everywhere
   * - ``titles_ambiguous``
     - ``add(w, kind="title")`` and ``add(w, kind="given")``
   * - ``given_name_titles``
     - ``add(w, kind="title", addresses="given")``
   * - ``after_given_titles``
     - ``add(w, kind="salutation", after_given=True)``
   * - ``title_modifiers``
     - ``add(w, kind="modifier")``
   * - ``title_styles``
     - ``add(w, kind="style")``
   * - ``title_phrases``
     - ``attaches=[...]`` on the first word's title reading, naming the
       title words or kinds it pairs with
   * - ``suffix_acronyms``
     - ``add(w, kind="credential")``
   * - ``suffix_acronyms_ambiguous``
     - a credential and a ``family`` reading
   * - ``suffix_words``
     - ``add(w, kind="suffix")``, or ``generation`` for a word that
       numbers its bearer (read by the ``generation`` view)
   * - ``suffix_words_ambiguous``
     - a ``generation`` reading with ``title_case_is_name=True`` and a
       ``family`` reading (2.x leaned every such word by its case)
   * - ``agnomens``
     - a ``family`` reading, then ``add(w, kind="agnomen")``, an agnomen
       needing the name reading that gates it
   * - ``honorific_tails``
     - ``attached="after"`` on the suffix reading
   * - ``particles``
     - ``add(w, kind="particle")``, or a finer particle kind
   * - ``particles_ambiguous``
     - a particle and a ``given`` reading, so
       ``remove(particles_ambiguous=...)`` is ``remove(w, kind="given")``
   * - ``conjunctions``
     - ``add(w, kind="conjunction")``
   * - ``conjunctions_ambiguous``
     - ``may_be_initial=True`` on the conjunction reading
   * - ``bound_given_names``
     - ``add(w, kind="bound_given")``
   * - ``given_name_abbreviations``
     - ``add(w, kind="given", same_as="<full name>")``
   * - ``maiden_markers``
     - ``add(w, kind="birth_marker")``, a phrase whole (``"z domu"``)
   * - ``surnames``, ``given_names``, ``capitalization_exceptions``
     - unchanged, fields still; ``add``/``remove`` no longer take the
       two lists, which join with ``lexicon | Lexicon(surnames={...})``

A ``Lexicon`` pickled by 2.x holds the compiled sets, and 3.1 refuses
it, as it refuses a ``Parser`` or a locale pack holding one:
:ref:`migrate-pickles` says which release loads which pickle.

.. _migrate-constants:

Vocabulary constants → Lexicon.words
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Through 2.x each default word list was a module constant, frozen since
2.2: ``from nameparser.config.titles import TITLES``. 3.0 removes those
modules, which 2.8.1 warns of, and a lexicon lists its words instead,
in the reading kinds it is configured by. Each 2.x constant is the call
beside it, with ``d = Lexicon.default()``: a ``words`` call, or a
comprehension over ``words`` and ``readings_of`` where the compiler
derives the set from more than one reading (a title word with a
``given`` reading and no particle reading reads as a title only inside
a title phrase), and for ``TITLE_PHRASES`` a note, since no call lists
it:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - 2.x constant
     - 3.0
   * - ``TITLES`` and ``TITLES_AMBIGUOUS``, together
     - ``d.words(kind="title")``
   * - ``TITLES_AMBIGUOUS``
     - ``[w for w in d.words(kind="title") if any(r.kind == "given" for r in d.readings_of(w)) and not any(r.category == "particle" for r in d.readings_of(w))]``
   * - ``TITLES``
     - ``[w for w in d.words(kind="title") if not (any(r.kind == "given" for r in d.readings_of(w)) and not any(r.category == "particle" for r in d.readings_of(w)))]``
   * - ``GIVEN_NAME_TITLES``
     - ``d.words(kind="title", addresses="given")``
   * - ``AFTER_GIVEN_TITLES``
     - ``d.words(kind="salutation", after_given=True)``
   * - ``TITLE_MODIFIERS``
     - ``d.words(kind="modifier")``
   * - ``TITLE_STYLES``
     - ``d.words(kind="style")``
   * - ``TITLE_PHRASES``
     - No call: each two-word phrase is compiled from a title reading's
       ``attaches`` property (``readings_of("chief")`` shows
       ``properties=(('attaches', ('military', 'office')),)``), and the
       phrases are not listed
   * - ``PARTICLES``
     - ``d.words(kind="particle")``
   * - ``NON_GIVEN_NAME_PARTICLES``
     - ``[w for w in d.words(kind="particle") if not any(r.kind == "given" for r in d.readings_of(w))]``
   * - ``CONJUNCTIONS``
     - ``d.words(kind="conjunction")``
   * - ``CONJUNCTIONS_AMBIGUOUS``
     - ``d.words(kind="conjunction", may_be_initial=True)``
   * - ``BOUND_GIVEN_NAMES``
     - ``d.words(kind="bound_given")``
   * - ``GIVEN_NAME_ABBREVIATIONS``
     - ``[w for w in d.words(kind="given") if any(r.kind == "given" and dict(r.properties).get("same_as") for r in d.readings_of(w))]``
   * - ``MAIDEN_MARKERS``
     - ``d.words(kind="birth_marker")``
   * - ``SUFFIX_ACRONYMS``
     - ``d.words(kind="suffix", acronym=True)``
   * - ``SUFFIX_WORDS``
     - ``d.words(kind="suffix", acronym=False)``
   * - ``SUFFIX_ACRONYMS_AMBIGUOUS``
     - ``[w for w in d.words(kind="suffix", acronym=True) if any(r.category == "name" and not (r.kind == "given" and "same_as" in dict(r.properties)) for r in d.readings_of(w))]``
   * - ``SUFFIX_WORDS_AMBIGUOUS``
     - ``[w for w in d.words(kind="suffix", acronym=False) if any(r.category == "name" and not (r.kind == "given" and "same_as" in dict(r.properties)) for r in d.readings_of(w))]``
   * - ``AGNOMENS``
     - ``d.words(kind="agnomen")``
   * - ``GLUED_HONORIFICS``
     - ``d.words(kind="suffix", attached="after")``
   * - ``CAPITALIZATION_EXCEPTIONS``
     - ``dict(d.capitalization_exceptions)``
   * - ``KOREAN_SURNAMES``
     - ``d.surnames``

``KOREAN_SURNAMES`` was ``nameparser.config.surnames``'s, the one
vocabulary module 3.0 makes private rather than removes, which 2.8.2
warns of: ``Lexicon.default().surnames`` holds the same words, on 2.x as
in 3.0.

To change a default word list, configure a lexicon and hand it to a
parser:

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> parse("Dean Smith").given          # a title only in a phrase
    'Dean'
    >>> dean_parser = Parser(lexicon=Lexicon.default().remove("dean", kind="given"))
    >>> dean_parser.parse("Dean Smith").title
    'Dean'

See :doc:`customize` for the full set of knobs.

.. _migrate-policy-settings:

Behavior and render settings → Policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Behavior and render scalars map onto :class:`~nameparser.Policy` (or a
rendering argument, where the 3.0 equivalent isn't config at all):

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - 1.x/2.x ``Constants``
     - 3.0 equivalent
     - Note
   * - ``patronymic_name_order``
     - ``Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC,
       PatronymicRule.TURKIC}))``
     - v1's single flag enabled both detectors at once; pick one rule
       (or a locale pack, see :doc:`locales`) if you only want one
       tradition
   * - ``middle_name_as_last``
     - ``Policy.middle_as_family``
     -
   * - ``nickname_delimiters``
     - ``Policy.nickname_delimiters``
     - Was a dict of named sentinels; now a plain ``frozenset`` of
       ``(open, close)`` pairs. The defaults gained the
       typographic pairs of :issue:`273` (smart quotes, guillemets, CJK brackets, ...)
       in 2.0 (:ref:`brackets`)
   * - ``maiden_delimiters``
     - ``Policy.maiden_delimiters``
     - Same shape change as ``nickname_delimiters``. Precedence
       differs: a pair listed here wins over ``nickname_delimiters``,
       where 1.x and 2.x's ``HumanName`` parsed a pair in both buckets
       as ``nickname`` (:ref:`brackets`)
   * - ``regexes.bidi``
     - ``Policy.strip_bidi``
     - ``regexes.bidi = False`` becomes ``Policy(strip_bidi=False)``
       (:ref:`strip-flags`)
   * - ``regexes.emoji``
     - ``Policy.strip_emoji``
     - ``regexes.emoji = False`` becomes ``Policy(strip_emoji=False)``
       (:ref:`strip-flags`)
   * - ``force_mixed_case_capitalization``
     - ``capitalized(force=True)``
     - The stored default is gone; pass ``force`` at the call site.
       v1's ``capitalize(force=True)`` already worked that way — this
       constant only supplied the default for calls that omitted it
   * - ``capitalize_name``
     - *(no equivalent)*
     - ``parse()`` never capitalizes automatically; call
       ``.capitalized()`` explicitly on the result instead

Every other ``regexes.*`` entry (``word``, ``spaces``, and the rest of
the compiled-pattern proxy) has no 3.0 replacement — parsing behavior
is configured entirely through named ``Policy`` fields now, not by
handing the parser a regex — and the ``nameparser.config.regexes``
module those entries came from is gone too (:ref:`migrate-removed`).

.. _migrate-pickles:

Pickles
-------

Which release loads a pickle depends on the object and on the release
that wrote it:

.. list-table::
   :header-rows: 1
   :widths: 22 14 18 18 28

   * - Pickled object
     - Written by
     - Under 3.0
     - Under 3.1
     - What to do
   * - ``HumanName`` or ``Constants``
     - 1.x or 2.x
     - does not load
     - does not load
     - Store ``parse(text).as_dict()`` or the original string; pickle
       the ``Parser`` in place of a ``Constants``
   * - ``Lexicon``, ``Parser`` or locale pack
     - 2.6 or earlier
     - ``ValueError``
     - ``ValueError``
     - Build the object again
   * - ``Lexicon``, ``Parser`` or locale pack
     - 2.7 or 2.8
     - loads, with a ``DeprecationWarning``, unless edited in a way
       no readings express (below)
     - ``ValueError``
     - Load it under 3.0 and pickle it again there
   * - ``Policy``
     - 2.5 or earlier
     - ``ValueError``
     - ``ValueError``
     - Build the object again
   * - ``Policy``
     - 2.6 to 2.8
     - loads
     - loads
     - Nothing
   * - ``Policy``, ``PolicyPatch``, and anything holding a ``Lexicon``
     - 3.1
     - ``ValueError``
     - loads
     - Keep a 3.0 copy while 3.0 must read it (below)
   * - ``ParsedName``
     - 2.x
     - loads, rendering as 2.x did
     - loads, rendering as 2.x did
     - Parse the text again to render it as written
   * - any of the rows above but the first
     - 3.0
     - loads
     - loads, keeping 3.0's vocabulary, save a caller's word written with a
       tatweel (below)
     - Build a new ``Parser()`` for 3.1's readings

A ``HumanName`` or a ``Constants``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Neither class exists in 3.0, so a pickle of one has nothing to load
into and fails. Store what a ``HumanName`` was read
from or read as, and pickle the ``Parser`` where 2.x code pickled a
``Constants``.

A ``Lexicon``, ``Parser`` or locale pack from 2.x
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A 2.x ``Lexicon`` pickle holds the compiled sets, where a 3.0 one holds
readings, and a ``Parser`` or a locale pack holds a ``Lexicon``. What
loads it depends on the release that wrote it:

- **Written by 2.7 or 2.8.** 3.0 loads it, translating it onto
  readings and raising a ``DeprecationWarning`` that says 3.1 will
  refuse it, and 3.1 refuses it with a ``ValueError`` saying which
  releases wrote it. Load it under 3.0 and pickle the loaded object
  again there (``pickle.dumps(obj)``). If 3.0 refuses the pickle too,
  as it refused an edited ``Lexicon`` whose sets no readings express,
  build the object again.
- **Written by 2.6 or earlier.** No 3.x release loads it, which the
  error says by naming the fields its layout lacks, so build that
  object again.

A re-pickled object keeps the vocabulary it was first pickled with, not
this release's; build a new ``Parser()`` for that.

Between 3.0 and 3.1
~~~~~~~~~~~~~~~~~~~

A pickle keeps the vocabulary of the release that wrote it. A
``Parser`` or locale pack pickled by 3.0 loads under 3.1 and reads and
matches as 3.0 did: it reads ``Md. Rahim Uddin`` with the title
``Md.``, does not split the Thai title off ``นายสมชาย``, finds no
familiar form between ``Bill`` and ``William``, and a pickled
``locales.NE`` lacks the ``initials_as_family`` 3.1 gives it. Build the
object again under 3.1 to read the 3.1 way.

A 3.0 ``Lexicon`` or ``Parser`` holding a word a caller added with an
Arabic tatweel (``ـ``) raises ``ValueError`` under 3.1, which deletes
the tatweel when it normalizes a word (:issue:`1151`): build it again
with the same ``add()`` calls.

The other way, 3.0.x refuses with ``ValueError`` anything holding a
``Lexicon``, ``Policy`` or ``PolicyPatch`` pickled by 3.1, a bare
``Policy()`` and a locale pack included: 3.1's vocabulary has readings
3.0 does not take, its ``Policy`` has two new fields, and
``Script.CYRILLIC`` is new. A ``ParsedName`` or ``Ambiguity`` loads
both ways.

Pickles between 2.x releases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The same refusals arrived inside 2.x. A ``Lexicon``, ``Policy`` or
``Parser`` pickled by 2.5 or earlier raises ``ValueError`` on load
since 2.6, each having gained a field; re-pickle after upgrading. A
``Lexicon``, ``Parser`` or locale pack pickled by 2.6 raises the same
way since 2.7.

A ``ParsedName`` from 2.x
~~~~~~~~~~~~~~~~~~~~~~~~~

A :class:`~nameparser.ParsedName` pickled by 2.x has no ``order`` and
renders exactly as it did under 2.x, while a fresh parse of the same text
renders as written (:ref:`migrate-3-0-rendering`). ``order`` is left
out of ``==`` and :meth:`~nameparser.ParsedName.comparison_key`, so it
never makes the two differ.

What else can: the loaded name is the reading of the release that
pickled it. Where that release read the name as this one does, the
fields and ``comparison_key()`` agree, and ``==`` holds too where the
words carry the same vocabulary tags, which it compares. A
``parse("Dr. John Smith, Jr.")`` pickled by 2.0 has the same fields and
key as a fresh parse and is not ``==`` to it, 2.0 having tagged ``Dr.``
with its suffix readings as well; one pickled by 2.3 or later is.

.. _migrate-comparison:

Comparison
----------

``HumanName.__eq__``/``__hash__`` were deprecated in 1.3.0 and removed
in 2.0, silently, and 3.0 has no ``HumanName`` at all. A
:class:`~nameparser.ParsedName` is never equal to a string, so grep for
``==`` wherever you compare names, and use
``matches()`` for "is this the same name?" and ``comparison_key()`` for
dedup, dict keys, and sorting — both work as ``HumanName``'s did:

.. code-block:: python

    hn = HumanName("de la Vega, Juan")
    hn.matches("Juan de la Vega")       # True

.. doctest::

    >>> vega = parse("de la Vega, Juan")
    >>> vega == "Juan de la Vega", vega.matches("Juan de la Vega")
    (False, True)
    >>> vega.comparison_key() == parse("Juan de la Vega").comparison_key()
    True

One behavior changed underneath both methods: components now fold with
``str.casefold()`` instead of ``str.lower()``, so more Unicode
case-pairs compare equal than did under 1.4. The change is strictly
more permissive — anything 1.4 matched still matches:

.. doctest::

    >>> parse("Anna STRASSE").matches("Anna Straße")
    True

.. _migrate-behavior:

Behavior changes
-----------------

Beyond the API surface mapped above, parse *outputs* differ between 1.4
and 3.2 for specific input shapes. The ones listed here, release by
release, are the shapes worth checking your fixtures for; the full
list, with reasoning, is in each release's section of
:doc:`release_log`, the 3.0, 3.1 and 3.2 ones included.

.. list-table::
   :header-rows: 1
   :widths: 12 60 28

   * - Release
     - What moved
     - List
   * - 2.0
     - A recognized suffix or title stays in its own field; maiden
       names
     - :ref:`migrate-2-0`
   * - 2.1
     - Names in East Asian script: family first, Korean names split,
       the middle dot
     - :ref:`migrate-2-1`
   * - 2.3
     - Titles that address by given name; a trailing title
     - :ref:`2.3 <migrate-2-3>`
   * - 2.4
     - Unlisted credentials, one-letter connectives, salutations, the
       case of credentials
     - :ref:`2.4 <migrate-2-4>`
   * - 2.5
     - A title before a family comma, junior and senior words, a
       particle after the given name
     - :ref:`2.5 <migrate-2-5>`
   * - 2.6
     - Given names written short, a salutation after the given name,
       invisible characters
     - :ref:`2.6 <migrate-2-6>`
   * - 2.7
     - A title that is also a given name, title phrases, joined
       credentials
     - :ref:`2.7 <migrate-2-7>`
   * - 2.8
     - More titles that are also names, the royal title phrases
     - :ref:`2.8 <migrate-2-8>`
   * - 3.0
     - Rendering as written, initials in East Asian script, particles,
       credentials and titles
     - :ref:`migrate-3-0`
   * - 3.1
     - Runs of initials, words glued at a full stop, commas in other
       scripts, case repair, titles and particles in other scripts,
       ``Md``, Thai names, credentials after a comma
     - :ref:`migrate-3-1`
   * - 3.2
     - Dutch ``Oude``, Malaysian ``a/l``, ``a/p`` and ``anak``
     - :ref:`migrate-3-2`

Each entry says what it compares with. The lists of readings through
3.0 give what 1.4 read, so they are written for code coming from 1.x: a
release between may have read the name a third way, which the release
log gives. 3.0's rendering and initials sections compare with 2.8, and
each 3.1 and 3.2 entry names the releases that read the name the old way.
Coming from 2.8, read the 3.0, 3.1 and 3.2 lists, and the release log's 3.0 section
too: a reading that a 2.x release moved and 3.0 moved back to 1.4's is
in the log and not in these lists.

If you want to see the difference on your own data rather than
ours, ``tools/differential/compare.py`` in the source repository diffs
any released version's parses against the source tree over the corpora
beside it, or over a file of your own names (``--corpus``). It is development
tooling, not part of the installed package — see its README.

.. _migrate-2-0:

Changed in 2.0
~~~~~~~~~~~~~~

These are the shapes worth grepping your own fixtures for, because a
recognized suffix or title now stays in its own field instead of
landing in the given or family name:

.. doctest::

    >>> parse("Andrews, MD").family, parse("Andrews, MD").suffix
    ('Andrews', 'MD')
    >>> parse("Johnson PhD").given, parse("Johnson PhD").suffix
    ('Johnson', 'PhD')

Under 1.4 those read ``title="MD"``/``first="Andrews"`` and
``first="Johnson"``/``last="PhD"`` respectively. The dotted
``"Andrews, M.D."`` read suffix ``M.D.`` from 2.0 through 3.0, where
1.4 read ``first="M.D."``, and moved again in 3.1
(:ref:`migrate-3-1-initials-credential`).

Two more to check for:
a maiden marker now fills the ``maiden`` field rather than being folded
into the middle or family name (``"Jane Smith née Jones"``), and with a
custom suffix delimiter configured, a no-space delimiter group renders
whole (``"RN/CRNA"``) where 1.x split it (``"RN, CRNA"``) — the role
assignment is identical, only the rendered string differs.

.. _migrate-2-1:

Changed in 2.1: East Asian names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

2.1 adds three more: a name written in East Asian script is read
family-first, an unspaced Korean name is split into surname and given
name, and the katakana middle dot separates tokens the way a space
does (:ref:`east-asian-names` explains the conventions).

.. doctest::

    >>> parse("毛 泽东").family
    '毛'
    >>> parse("김민준").family, parse("김민준").given
    ('김', '민준')

1.4 read the first as ``first="毛"``/``last="泽东"``, and left the
second whole in ``first``.

An unspaced Chinese or Japanese name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A third shape changes even though nothing splits it. 1.4 routed a lone
token to ``first`` whatever it was, so an unspaced Chinese or Japanese
name landed there entire; 2.1 reads it as native-script CJK and puts it
in the family name instead. Nothing is segmented — Han splitting is
opt-in through a locale pack (:doc:`locales`) — but the field the whole
string arrives in is different:

.. doctest::

    >>> parse("毛泽东").family, parse("毛泽东").given
    ('毛泽东', '')
    >>> parse("山田太郎").family, parse("山田太郎").given
    ('山田太郎', '')

Both were ``first`` under 1.4. If you parse unspaced CJK and read the
given name, that is the change most likely to reach you, and it is
silent — the string is intact, just in the other field.

Japanese kana
^^^^^^^^^^^^^

Japanese kana carries the same order rule, which widens both shapes
past the wholly-Han text described above. A name that mixes kanji with
hiragana or katakana is read family-first, and a lone kana-bearing
token moves from the given name to the family name exactly as
``毛泽东`` does:

.. doctest::

    >>> parse("高橋 みなみ").family, parse("高橋 みなみ").given
    ('高橋', 'みなみ')
    >>> parse("山田 エミ").family
    '山田'
    >>> parse("高橋みなみ").family, parse("高橋みなみ").given
    ('高橋みなみ', '')

1.4 read the spaced ones as ``first="高橋"``/``last="みなみ"`` and
``first="山田"``/``last="エミ"``, and put the unspaced one whole in
``first``.

A name written *wholly* in katakana is deliberately
left alone — it may be a transcribed foreign name already in
given-first order or a Japanese name's reading written family-first,
and the script cannot tell which (see :ref:`east-asian-names` to opt
in) — so ``parse("マイケル ジャクソン")`` reads given ``マイケル``,
family ``ジャクソン``, as 1.4 did.

The katakana middle dot
^^^^^^^^^^^^^^^^^^^^^^^

One more shape changes for a different reason: the katakana middle dot
``・``, which divides the parts of such a transcription, is now a token
separator rather than an ordinary character. 1.4 saw one token and put
it in ``first``; 2.1 sees two:

.. doctest::

    >>> parse("マイケル・ジャクソン").given
    'マイケル'
    >>> parse("マイケル・ジャクソン").family
    'ジャクソン'
    >>> parse("高橋・一郎").family, parse("高橋・一郎").given
    ('高橋', '一郎')

The two divide the same way and land in opposite fields, because the
katakana pair keeps its source order while the kanji pair takes the
family-first rule. Separating also changes the ``nickname`` and
other fields, which join their words with a space: the nickname in
``"山田 太郎 (マイケル・ジャクソン)"`` was ``"マイケル・ジャクソン"``
under 1.4 and is ``"マイケル ジャクソン"`` now.

What 2.1 through 2.8 rendered
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Through 2.8 three of these shapes also changed what the name *rendered*
as, which 3.0 undid (:ref:`migrate-3-0-rendering`):

- **The split Korean name.** ``str(parse("김민준"))`` was ``"민준 김"``,
  where 1.4's ``str(HumanName("김민준"))`` was ``"김민준"``, because
  the split inserted a token boundary that the default format then
  wrote given-name-first. 3.0 renders ``"김민준"`` again.
- **The spaced kanji and kana names.** ``str(parse("高橋 みなみ"))``
  was ``"みなみ 高橋"``, where 1.4 and 3.0 write ``"高橋 みなみ"``.
- **The middle dots.** The dot came back as a space
  (``str(parse("マイケル・ジャクソン"))`` was ``"マイケル ジャクソン"``),
  the Chinese interpunct of the next section included; 3.0 renders it
  with its dot, as 1.4 did.

.. doctest::

    >>> str(parse("高橋 みなみ")), str(parse("マイケル・ジャクソン"))
    ('高橋 みなみ', 'マイケル・ジャクソン')

Turning the East Asian readings off
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The switch is on the ``Policy`` (:ref:`east-asian-defaults`):
``Parser(policy=Policy(script_orders=(), segment_scripts=frozenset()))``
restores 1.4's reading of every shape above that turns on order or
splitting. The middle dots are the exception: both the katakana dot
and the Chinese interpunct ``·`` (U+00B7, dividing a transcription
like ``威廉·莎士比亚``, and a separator only between classified-script
characters — each side judged on its own — where the katakana dot is
unconditional) are decided
in tokenization rather than by policy, so a name written with either
still divides at the dot whatever those two fields are set to.

Changed in 2.3 through 2.8
~~~~~~~~~~~~~~~~~~~~~~~~~~

Later releases moved more 1.4 readings; 2.1 and 2.2 read every one of
them as 1.4 did. The release
log's 2.3 to 2.8 sections carry the reasoning; these are the shapes to
grep your fixtures for, with what 1.4 read, under the release that
moved each. A release's examples follow its list, in the list's order.

.. _migrate-2-3:

2.3
^^^

- ``"Her Majesty Queen Elizabeth"``, ``"His Royal Highness Prince Harry"`` — a lone
  name after a title that addresses by given name is the given name:
  1.4 read last ``Elizabeth`` and ``Harry``. 2.3 matched a run of titles
  by its last one (``Her Majesty Queen``, ``Rev Sir``) and added titles
  that address that way (``Prince``, ``Princess``, ``Swami``, ``Guru``
  and others). Other titles still leave the name the family name
  (``"Dr Harry"``). Since 2.7 a bare ``Prince`` or ``Princess`` is a
  given name (:ref:`2.7 <migrate-2-7>`); behind a style, as here, it is
  still a title.
- ``"Dr King Jr"`` — 1.4 read title ``Dr King``, last ``Jr``.
- ``"John Smith Prof."`` — a trailing period-marked title: 1.4
  read last ``Prof.``, middle ``Smith``.

.. doctest::

    >>> parse("Her Majesty Queen Elizabeth").given
    'Elizabeth'
    >>> parse("His Royal Highness Prince Harry").given
    'Harry'
    >>> king = parse("Dr King Jr")
    >>> king.title, king.family, king.suffix
    ('Dr', 'King', 'Jr')
    >>> parse("John Smith Prof.").title
    'Prof.'

.. _migrate-2-4:

2.4
^^^

- ``"Jack MA"`` — an ambiguous acronym in capitals in a mixed-case
  name is a credential: 1.4 read last ``MA``. ``"Jack Ma"`` and
  ``"JACK MA"`` are unchanged.
- ``"jose e maria santos"`` — ``e`` in a name written wholly in
  one case is an initial (``y`` still joins): 1.4 read first ``jose e
  maria``.
- ``"van der Berg, PhD"`` — 1.4 read first ``van``, last ``der
  Berg``.
- ``"Josep Carod i Rovira"`` — ``i`` links two surnames in a
  mixed-case name: 1.4 read middle ``Carod i``, last ``Rovira``.
- ``"Jane Smith N.C.C."`` — an unlisted dotted credential after a
  full name: 1.4 read last ``N.C.C.``, middle ``Smith``. ``"Jack
  X.Y.Z."`` is unchanged.
- ``"Jane Smith, LEED AP"`` — an unlisted all-caps credential
  after a comma: 1.4 read first ``LEED``, middle ``AP``, last ``Jane
  Smith``.
- ``"Eric H. Holder Jr. Attorney General"`` and ``"Eric H. Holder, Jr.,
  Attorney General"`` — a title after a credential is a title:
  1.4 read middle ``H. Holder Jr. Attorney``, last ``General``, and
  suffix ``Jr., Attorney General``.
- ``"Steven Hardman, RN - CRNA"`` — a credential after a comma
  starts a run of credentials, and since 2.7 the hyphen standing alone
  parts it as a comma (suffix ``RN, CRNA``): 1.4 read first ``RN``,
  middle ``-``, last ``Steven Hardman``, suffix ``CRNA``.
- ``"John van der Berg Prof."`` — 1.4 read last ``van der Berg
  Prof.``.
- ``"Liam Ó Murchú"`` — the Irish particles ``Ó``, ``Ní`` and
  ``Ua`` join the surname: 1.4 read middle ``Ó``, last ``Murchú``.
- ``"Herra Väinö Johansson"`` — salutations in Finnish,
  Icelandic, Malay and other languages are titles: 1.4 read first
  ``Herra``, middle ``Väinö``.
- ``"山田 ﾀﾛｳ"`` — halfwidth katakana reads as katakana: 1.4 read
  first ``山田``, last ``ﾀﾛｳ``.
- capitalizing ``"john smith md"``, ``"john smith phd"`` and
  ``"JANE DOE MBA"`` — 1.4 wrote ``M.D.``, ``Ph.D.`` and ``Mba``;
  credentials are now written the usual way (``MD``, ``PhD``, ``MBA``).
- ``initials()`` on ``"john e smith"`` — 1.4 gave ``j. s.``; a
  one-letter connective read as an initial now contributes one.

.. doctest::

    >>> parse("Jack MA").suffix
    'MA'
    >>> parse("jose e maria santos").middle
    'e maria'
    >>> parse("van der Berg, PhD").family
    'van der Berg'
    >>> parse("Josep Carod i Rovira").family
    'Carod i Rovira'
    >>> parse("Jane Smith N.C.C.").suffix
    'N.C.C.'
    >>> parse("Jane Smith, LEED AP").suffix
    'LEED AP'
    >>> holder = parse("Eric H. Holder Jr. Attorney General")
    >>> holder.title, holder.family, holder.suffix
    ('Attorney General', 'Holder', 'Jr.')
    >>> parse("Eric H. Holder, Jr., Attorney General").title
    'Attorney General'
    >>> parse("Steven Hardman, RN - CRNA").suffix
    'RN, CRNA'
    >>> parse("John van der Berg Prof.").family
    'van der Berg'
    >>> parse("Liam Ó Murchú").family
    'Ó Murchú'
    >>> parse("Herra Väinö Johansson").title
    'Herra'
    >>> parse("山田 ﾀﾛｳ").family
    '山田'
    >>> str(parse("john smith md").capitalized(force=True))
    'John Smith MD'
    >>> str(parse("john smith phd").capitalized())
    'John Smith PhD'
    >>> str(parse("JANE DOE MBA").capitalized())
    'Jane Doe MBA'
    >>> parse("john e smith").initials()
    'j. e. s.'

.. _migrate-2-5:

2.5
^^^

- ``"Dr. Smith, John"`` — a listed title before a family comma is
  a title: 1.4 read last ``Dr. Smith``. ``"Gov Smith"`` — ``Gov``
  is a title: 1.4 read first ``Gov``.
- ``"Antonio Pavlović mlađi"`` — junior and senior in more than
  forty languages are suffixes: 1.4 read middle ``Pavlović``, last ``mlađi``.
- ``"John Smith II, AD"`` — a credential after a generational
  suffix and a comma: 1.4 read first ``AD``, last ``John Smith``.
- ``"John III, Sir"`` and ``"Smith, Sir"`` — the name before
  a comma and a given-name title is the given name: 1.4 read last
  ``John`` and ``Smith``.
- ``"Ivoi, Paul d'"`` — a particle after the given name joins the
  surname: 1.4 read middle ``d'``.
- ``"jose j y lopez"`` — a lone letter in a one-case name reads as
  in capitals: 1.4 read last ``j y lopez``.
- ``"Bapak Dwi Putro"`` — the salutations ``bapak`` and ``owura``
  are titles: 1.4 read first ``Bapak``, middle ``Dwi``.
- capitalizing ``"jacobus henricus van 't hoff"`` — 1.4
  wrote ``van 'T Hoff``.

.. doctest::

    >>> dr = parse("Dr. Smith, John")
    >>> dr.title, dr.given, dr.family
    ('Dr.', 'John', 'Smith')
    >>> parse("Gov Smith").title
    'Gov'
    >>> parse("Antonio Pavlović mlađi").suffix
    'mlađi'
    >>> parse("John Smith II, AD").suffix
    'II, AD'
    >>> parse("John III, Sir").given
    'John'
    >>> parse("Smith, Sir").given
    'Smith'
    >>> parse("Ivoi, Paul d'").family
    "d' Ivoi"
    >>> parse("jose j y lopez").middle
    'j y'
    >>> parse("Bapak Dwi Putro").title
    'Bapak'
    >>> str(parse("jacobus henricus van 't hoff").capitalized(force=True))
    "Jacobus Henricus van 't Hoff"

.. _migrate-2-6:

2.6
^^^

- ``"Maria de Sa"`` and ``"John Smith SA"`` — ``Sa`` is no longer
  a credential: 1.4 read last ``de``, suffix ``Sa``, and suffix ``SA``.
- ``"Cllr John Smith"`` and ``"Dott.ssa Anna Bianchi"`` — ``Cllr``
  and the Italian abbreviated salutations are titles: 1.4 read first
  ``Cllr`` and ``Dott.ssa``, middle ``John`` and ``Anna``.
- ``"José Silva Júnior"`` — 1.4 read middle ``Silva``, last
  ``Júnior``.
- ``"John Smith, MD; PhD"`` — a semicolon between post-nominals
  reads as a comma: 1.4 read first ``MD;``, last ``John Smith``.
- ``"Mr Md Karim Uddin"`` and ``"Wm Smith"`` — ``Md`` and ``Wm``
  are the given names they abbreviate: 1.4 read title ``Mr Md`` and
  ``Wm``.
- ``"Doe, Jane Mrs"`` — a salutation ending the given name after a
  family comma is the title: 1.4 read middle ``Mrs``.
- A zero-width space or byte-order mark divides words as a space
  does: 1.4 kept it in the word beside it, so ``"\u200bDr. John Smith"``
  read first ``Dr.``.
- capitalizing ``"j.r.r. tolkien"`` — 1.4 wrote ``J.r.r.``;
  repair now capitalizes after a full stop or an ayn.

.. doctest::

    >>> parse("Maria de Sa").family
    'de Sa'
    >>> parse("John Smith SA").family
    'SA'
    >>> parse("Cllr John Smith").title
    'Cllr'
    >>> parse("Dott.ssa Anna Bianchi").title
    'Dott.ssa'
    >>> parse("José Silva Júnior").suffix
    'Júnior'
    >>> parse("John Smith, MD; PhD").suffix
    'MD; PhD'
    >>> md_karim = parse("Mr Md Karim Uddin")
    >>> md_karim.title, md_karim.given
    ('Mr', 'Md')
    >>> parse("Wm Smith").given
    'Wm'
    >>> parse("Doe, Jane Mrs").title
    'Mrs'
    >>> parse("\u200bDr. John Smith").title
    'Dr.'
    >>> str(parse("j.r.r. tolkien").capitalized())
    'J.R.R. Tolkien'

.. _migrate-2-7:

2.7
^^^

- ``"King Curtis"``, ``"Prince Fielder"``, ``"Sultan Khan"`` and
  ``"Sheikh Ahmed Khan"`` — a title that is also a given name is a
  title only inside a title phrase or behind a style (``"His Majesty
  King Henry"``), so a bare one opening the name is the first name: 1.4
  read title ``King``, ``Prince``, ``Sultan`` and ``Sheikh``. The same
  holds for ``Princess``, ``Sultana``, ``Shaikh``, ``Sheik``, ``Shekh``,
  ``Shaik``, ``Cheikh``, ``Mahdi``, ``Bard``, ``Buddha``, ``Siddha``,
  ``Gyani`` and ``Wing``, and for a lone qualifier such as ``Grand``.
  ``Lexicon.default().remove("king", kind="given")`` makes one a title
  everywhere.
- ``"Chief Justice John Roberts"`` and ``"Major General John Smith"``
  — a title phrase is one title: 1.4 read title ``Chief``, first
  ``Justice``, and first ``Major``, middle ``General John``.
- ``"Chas. Smith"`` and ``"Ma. Cristina Reyes"`` — a given name
  written short is the first name: 1.4 read title ``Chas.`` and ``Ma.``.
- ``"John Smith VI MD"`` and ``"Smith, John VI"`` — the numerals
  ``VI`` to ``X`` are suffixes as ``III`` is: 1.4 read last ``VI``,
  suffix ``MD``, and middle ``VI``.
- ``"John Smith, MD/PhD"`` and ``"John Smith, Pharm D"`` — a
  credential joined by a hyphen or slash, or split by a space, after a
  comma is a suffix: 1.4 read first ``MD/PhD``, and first ``Pharm``,
  middle ``D``, each with last ``John Smith``.
- ``"John Smith Ph. D. Jones"`` — 1.4 read last ``Jones``, suffix
  ``Ph. D.``.
- ``"Smith, John MA Jones"`` — a listed credential in capitals in
  a mixed-case name starts the suffix: 1.4 read middle ``Jones``, suffix
  ``MA``.
- ``"Pedro Alves Filho"`` and ``"Alexandre Dumas fils"`` — the
  Brazilian agnomens and ``fils`` are suffixes where the name has a word
  to spare: 1.4 read middle ``Alves`` and ``Dumas``, last ``Filho`` and
  ``fils``.
- ``"Andrew Perkins (JD)"`` — a bracketed credential its writing
  settles is a suffix: 1.4 read nickname ``JD``.
- ``"Jane Smith, Dr. / MD"`` — a hyphen or slash standing alone
  between post-nominals reads as a comma: 1.4 read first ``/``, last
  ``Jane Smith``.
- ``"Marie Bon Durand"`` and ``"Herren Hans"`` — ``Bon``, ``Dí``
  and ``Heer`` are no longer particles, nor ``Herren`` and ``Heren``
  titles: 1.4 read last ``Bon Durand`` and title ``Herren``.

.. doctest::

    >>> [parse(n).given for n in ("King Curtis", "Prince Fielder",
    ...     "Princess Diana", "Sultan Khan", "Sultana Begum",
    ...     "Sheikh Ahmed Khan", "Shaikh Ahmed Khan", "Sheik Ahmed",
    ...     "Shekh Ahmed", "Shaik Ahmed", "Cheikh Anta Diop",
    ...     "Mahdi Karimi", "Bard Larsen", "Buddha Bahadur Tamang",
    ...     "Siddha Raj Joshi", "Gyani Maya Gurung", "Wing Lau")]
    ... # doctest: +NORMALIZE_WHITESPACE
    ['King', 'Prince', 'Princess', 'Sultan', 'Sultana', 'Sheikh', 'Shaikh',
     'Sheik', 'Shekh', 'Shaik', 'Cheikh', 'Mahdi', 'Bard', 'Buddha',
     'Siddha', 'Gyani', 'Wing']
    >>> parse("His Majesty King Henry").title
    'His Majesty King'
    >>> parse("Chief Justice John Roberts").title
    'Chief Justice'
    >>> parse("Major General John Smith").title
    'Major General'
    >>> parse("Chas. Smith").given, parse("Ma. Cristina Reyes").given
    ('Chas.', 'Ma.')
    >>> parse("John Smith VI MD").suffix, parse("Smith, John VI").suffix
    ('VI MD', 'VI')
    >>> parse("John Smith, MD/PhD").suffix
    'MD/PhD'
    >>> parse("John Smith, Pharm D").suffix
    'Pharm D'
    >>> parse("John Smith Ph. D. Jones").suffix
    'Ph. D. Jones'
    >>> parse("Smith, John MA Jones").suffix
    'MA Jones'
    >>> parse("Pedro Alves Filho").suffix
    'Filho'
    >>> parse("Alexandre Dumas fils").family
    'Dumas'
    >>> parse("Andrew Perkins (JD)").suffix
    'JD'
    >>> parse("Jane Smith, Dr. / MD").given
    'Jane'
    >>> parse("Marie Bon Durand").family
    'Durand'
    >>> parse("Herren Hans").given
    'Herren'

.. _migrate-2-8:

2.8
^^^

- ``"Marquis Johnson"`` and ``"Johnson, Marquise"`` — ``Marquis``
  and ``Marquise`` are titles only inside a title phrase, as ``King`` is
  since 2.7 (``"Marquis of Queensberry"`` keeps the title): 1.4 read
  title ``Marquis`` and ``Marquise``.
- ``"Deacon Jones"``, ``"Burgess Meredith"`` and ``"Ranger Smith"``
  — ``Deacon``, ``Burgess`` and ``Ranger`` are titles only inside a
  title phrase, as ``King`` is since 2.7 (``"Deacon of the Church Jane
  Smith"`` keeps the title): 1.4 read title ``Deacon``, ``Burgess`` and
  ``Ranger``.
- ``"Queen Latifah"`` and ``"Elizabeth II, Queen"`` — ``Queen`` is
  a title only inside a title phrase or behind a style (``"Her Majesty
  Queen Elizabeth"``), as ``King`` is since 2.7: 1.4 read title
  ``Queen``, first ``Latifah``, and last ``Elizabeth``.
- ``"Prince Consort Albert"``, ``"Princess Royal Anne"`` and ``"Bales,
  Royal"`` — the royal title phrases are one title, and ``Royal``
  after a family comma is the first name: 1.4 read title ``Prince``,
  first ``Consort``; title ``Princess Royal``, last ``Anne``; and title
  ``Royal``, first ``Bales``.
- ``"Chancellor Smith"`` and ``"Lord Justice Leveson"`` —
  ``Chancellor`` is a title only inside a title phrase (``"Lord
  Chancellor John Smith"``), and ``Lord Justice`` and ``Lady Justice`` are
  one title: 1.4 read title ``Chancellor``, and title ``Lord``, first
  ``Justice``.

.. doctest::

    >>> parse("Marquis Johnson").given, parse("Johnson, Marquise").given
    ('Marquis', 'Marquise')
    >>> parse("Marquis of Queensberry").title
    'Marquis of Queensberry'
    >>> [parse(n).given for n in ("Deacon Jones", "Burgess Meredith",
    ...     "Ranger Smith")]
    ['Deacon', 'Burgess', 'Ranger']
    >>> parse("Deacon of the Church Jane Smith").title
    'Deacon of the Church'
    >>> parse("Queen Latifah").given, parse("Elizabeth II, Queen").given
    ('Queen', 'Queen')
    >>> consort = parse("Prince Consort Albert")
    >>> consort.title, consort.given
    ('Prince Consort', 'Albert')
    >>> parse("Princess Royal Anne").given, parse("Bales, Royal").given
    ('Anne', 'Royal')
    >>> parse("Chancellor Smith").given
    'Chancellor'
    >>> parse("Lord Chancellor John Smith").title
    'Lord Chancellor'
    >>> parse("Lord Justice Leveson").title
    'Lord Justice'

.. _migrate-3-0:

Changed in 3.0
~~~~~~~~~~~~~~

.. _migrate-3-0-rendering:

Rendering order and separators
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``str()`` and :meth:`~nameparser.ParsedName.render` with no argument
lay a name out in the order it was read in, recorded as
:attr:`ParsedName.order <nameparser.ParsedName.order>`, and keep the
separator its writer put between two words that stay side by side,
normalized: nothing stays nothing, any whitespace (the ideographic
space included) becomes one space, a dividing middle dot stays, and a
comma before a suffix stays. Through 2.8 every name rendered
given-name-first with its words joined by spaces:

.. doctest::

    >>> str(parse("김민준")), str(parse("威廉·莎士比亚"))
    ('김민준', '威廉·莎士比亚')
    >>> from nameparser import FAMILY_FIRST, Parser, Policy
    >>> str(Parser(policy=Policy(name_order=FAMILY_FIRST)).parse("Nagy Laszlo"))
    'Nagy Laszlo'
    >>> str(parse("John Smith, Jr.")), str(parse("Smith, John, Jr."))
    ('John Smith, Jr.', 'John Smith Jr.')

2.8 gave ``'민준 김'``, ``'威廉 莎士比亚'``, ``'Laszlo Nagy'`` and
``'John Smith Jr.'`` for the first four. A family comma is never kept,
so ``Smith, John`` still renders ``'John Smith'``. To keep 2.x's
output, pass 2.x's default as a spec: a spec you write renders exactly
as written, in its order and with its joiners.

.. doctest::

    >>> v2_spec = '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}'
    >>> parse("김민준").render(v2_spec)
    '민준 김'

A :class:`~nameparser.ParsedName` pickled by 2.x keeps 2.x's rendering
(:ref:`migrate-pickles`).

Initials in scripts without them
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:meth:`~nameparser.ParsedName.initials` gives nothing for a word
in Han, Hangul or kana, scripts with no initials, where 2.8 gave its
first character:

.. doctest::

    >>> parse("김민준").initials(), parse("Kim Minjun").initials()
    ('', 'K. M.')

Readings that moved
^^^^^^^^^^^^^^^^^^^

3.0 moved these 1.4 readings too. The release log's 3.0 section
carries the reasoning; these are the shapes to grep your fixtures for,
with what 1.4 read, by what moved. Each group's examples follow its
list, in the list's order.

Titles and given names written short
""""""""""""""""""""""""""""""""""""

- ``"Jean Dupont, Pr"`` and ``"Juan Pérez, Profesor"`` — the French and
  Spanish professor titles are titles: 1.4 read first ``Pr`` and
  ``Profesor``, last ``Jean Dupont`` and ``Juan Pérez``.
- ``"Maj Sjöwall"``, ``"Gen Goto"``, ``"Pharaoh Mwale"`` and ``"Saint
  Clair Soares"`` — a bare rank or ``Pharaoh``, ``Saint``, ``Sailor`` or
  ``Majesty`` opening a name is the given name: 1.4 read title ``Maj``,
  ``Gen``, ``Pharaoh`` and ``Saint``. ``"Brig Gen Mark Kimmitt"`` is one
  title: 1.4 read first ``Brig``.
- ``"Silva, Junior Carlos"`` — 1.4 read title ``Junior``, first
  ``Carlos``.
- ``"Hans Meier Priv.-Doz."`` — a listed title with a period or hyphen
  inside it ending a name is a title: 1.4 read middle ``Meier``, last
  ``Priv.-Doz.``.
- ``"Mohd. Shameem Khan"`` — Muhammad, Achmad, Francisco and Sheikh
  written short are given names: 1.4 read title ``Mohd.``, first
  ``Shameem``.
- ``"Jan Novák, MUDr"``, ``"Licenciado Juan Pérez"``, ``"Esra Oz, Assist
  Prof"``, ``"Engr Ahsen Ali"`` and ``"Anselm Crombach, Dipl.-Psych."``
  — titles no name bears are titles: 1.4 read first ``MUDr``,
  ``Licenciado``, ``Assist``, ``Engr`` and ``Dipl.-Psych.``.

.. doctest::

    >>> parse("Jean Dupont, Pr").title, parse("Juan Pérez, Profesor").title
    ('Pr', 'Profesor')
    >>> [parse(n).given for n in ("Maj Sjöwall", "Gen Goto", "Pharaoh Mwale",
    ...     "Saint Clair Soares")]
    ['Maj', 'Gen', 'Pharaoh', 'Saint']
    >>> parse("Brig Gen Mark Kimmitt").title
    'Brig Gen'
    >>> parse("Silva, Junior Carlos").given
    'Junior'
    >>> parse("Hans Meier Priv.-Doz.").title
    'Priv.-Doz.'
    >>> parse("Mohd. Shameem Khan").given
    'Mohd.'
    >>> [parse(n).title for n in ("Jan Novák, MUDr", "Licenciado Juan Pérez",
    ...     "Esra Oz, Assist Prof", "Engr Ahsen Ali",
    ...     "Anselm Crombach, Dipl.-Psych.")]
    ['MUDr', 'Licenciado', 'Assist Prof', 'Engr', 'Dipl.-Psych.']

Particles and compound names
""""""""""""""""""""""""""""

- ``"Otto Graf Lambsdorff"`` — ``Graf``, ``Gräfin``, ``Fürst`` and
  ``Prinz`` inside a surname join it, as ``Freiherr`` does: 1.4 read
  middle ``Graf``, last ``Lambsdorff``. Opening a name each is still a
  title (``"Graf Zeppelin"``).
- ``"Juan Sta. Maria Reyes"`` and ``"Juan Delos Reyes"`` — ``Sta.``,
  ``Sto.`` and the Filipino ``Delos`` are surname particles: 1.4 read
  middle ``Sta. Maria`` and ``Delos``, last ``Reyes``.
- ``"María del Carmen García"`` — a compound given name written with a
  particle is a middle name: 1.4 read last ``del Carmen García``.
- ``"طارق عبد العزيز"`` — ``عبد`` joins a listed name of God after it:
  1.4 read middle ``عبد``, last ``العزيز``.
- ``"John Smith y V"`` — a lone letter after a connective is part of
  the family: 1.4 read middle ``Smith``, last ``y``, suffix ``V``.

.. doctest::

    >>> parse("Otto Graf Lambsdorff").family
    'Graf Lambsdorff'
    >>> parse("Juan Sta. Maria Reyes").family, parse("Juan Delos Reyes").family
    ('Sta. Maria Reyes', 'Delos Reyes')
    >>> parse("María del Carmen García").middle
    'del Carmen'
    >>> parse("طارق عبد العزيز").family
    'عبد العزيز'
    >>> parse("John Smith y V").family
    'Smith y V'

Suffixes and credentials
""""""""""""""""""""""""

- ``"Ortega y Gasset VI"`` — 1.4 read first ``Ortega y Gasset``, last
  ``VI``.
- ``"John Smith (PhD, MBA)"`` and ``"Justin (JP) Stearns"`` — a
  bracketed clause of credentials is the suffix, and initials in
  brackets the nickname: 1.4 read nickname ``PhD, MBA`` and middle
  ``JP``.
- ``"Alexandre Dumas père"`` — 1.4 read middle ``Dumas``, last
  ``père``.
- ``"Jane Doe KC"`` and ``"Jane Doe MSW"`` — British post-nominals and
  several dozen common US credentials are suffixes: 1.4 read middle ``Doe``, last
  ``KC`` and ``MSW``.
- ``"Jane Smith PhD/NP-C"`` and ``"John Smith MA/PhD"`` — a joined
  credential is the suffix, a credential listed with its own joiner and
  a credential that is also a name beside one that is not included: 1.4
  read middle ``Smith``, last ``PhD/NP-C`` and ``MA/PhD``.
- ``"John Smith (Ma, PhD)"`` and ``"John Smith (Msc.Ed)"`` — 1.4 read
  nickname ``Ma, PhD`` and ``Msc.Ed``.
- ``"'Smitty' Jones Jr."`` — a nickname, one name word and a suffix read
  the word as the family: 1.4 read first ``Jones``, last ``Jr.``.
- ``"Mary Smith, Mst"`` — ``Mst`` after a name is a credential: 1.4
  read first ``Mst``, last ``Mary Smith``.

.. doctest::

    >>> parse("Ortega y Gasset VI").family
    'Gasset'
    >>> parse("John Smith (PhD, MBA)").suffix, parse("Justin (JP) Stearns").nickname
    ('PhD, MBA', 'JP')
    >>> parse("Alexandre Dumas père").suffix
    'père'
    >>> parse("Jane Doe KC").suffix, parse("Jane Doe MSW").suffix
    ('KC', 'MSW')
    >>> parse("Jane Smith PhD/NP-C").suffix, parse("John Smith MA/PhD").suffix
    ('PhD/NP-C', 'MA/PhD')
    >>> parse("John Smith (Ma, PhD)").suffix, parse("John Smith (Msc.Ed)").suffix
    ('Ma, PhD', 'Msc.Ed')
    >>> parse("'Smitty' Jones Jr.").family
    'Jones'
    >>> parse("Mary Smith, Mst").suffix
    'Mst'

Separators and case repair
""""""""""""""""""""""""""

- ``"John⁣Smith"`` — the invisible separator divides words: 1.4
  read first ``John⁣Smith``.
- ``"이서연·김민준"`` typed decomposed (NFD) — the interpunct divides
  it as it does the composed spelling: 1.4 read first
  ``이서연·김민준``.
- capitalizing ``"JOHN ST CLAIR"``, ``"JUAN DELA CRUZ"`` and ``"JOHN
  MACHADO"`` — 1.4 wrote ``st``, ``dela`` and ``MacHado``; saint and
  rank particles keep their capital, and a name opening Mac is
  title-cased unless the vocabulary records its casing (``MacDonald``).

.. doctest::

    >>> parse("John⁣Smith").family
    'Smith'
    >>> import unicodedata
    >>> nfd = parse(unicodedata.normalize("NFD", "이서연·김민준"))
    >>> nfd.given == unicodedata.normalize("NFD", "이서연")
    True
    >>> [str(parse(n).capitalized()) for n in ("JOHN ST CLAIR",
    ...     "JUAN DELA CRUZ", "JOHN MACHADO", "RONALD MACDONALD")]
    ['John St Clair', 'Juan Dela Cruz', 'John Machado', 'Ronald MacDonald']

.. _migrate-3-1:

Changed in 3.1
~~~~~~~~~~~~~~

Each entry names the releases that read the name the old way.

Runs of initials
^^^^^^^^^^^^^^^^

A given name written as a run of initials joined by full stops is read
as the initials, the first letter the given name and the rest the middle
name, where 1.4 through 3.0 read the run as one given name.
:meth:`~nameparser.ParsedName.initials` gives every letter of a run, in
the middle or family name too, where 1.4 through 3.0 gave its first.
``str()`` keeps the run as written:

.. doctest::

    >>> tolkien = parse("J.R.R. Tolkien")
    >>> tolkien.given, tolkien.middle, tolkien.initials(), str(tolkien)
    ('J.', 'R.R.', 'J. R. R. T.', 'J.R.R. Tolkien')
    >>> parse("Ana J.R. García").initials()
    'A. J. R. G.'

A dotted title before another title
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``U.S.``, ``U.K.`` and the German ``P.D.`` opening a name are part of the
title where another title the name keeps follows them, where 1.4 through
3.0 read them as the given name and the title after them as a middle
name. Before a name word they are not read as a title:

.. doctest::

    >>> judge = parse("U.S. District Judge Marc Thomas Treadwell")
    >>> judge.title, judge.given
    ('U.S. District Judge', 'Marc')
    >>> parse("U.S. Grant").title
    ''

Latin initials in Brahmic scripts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A Latin initial spelled in Devanagari, Bengali or another Brahmic script
from Devanagari to Sinhala (``एम.`` for M.) is a name word, where 1.4
through 3.0 read it as a title. Listed titles such as ``डा.`` are
unchanged:

.. doctest::

    >>> verma = parse("एम. एस. वर्मा")
    >>> verma.title, verma.given, verma.middle
    ('', 'एम.', 'एस.')

A word glued at a full stop
^^^^^^^^^^^^^^^^^^^^^^^^^^^

A name glued to the title or initial before it at a full stop divides
there, where 1.4 through 3.0 read the two as one word, so ``Dr.John
Smith`` had no given name. ``str()`` keeps the word as written, and a
word in lower case after the stop (``Dr.med``) stays whole. A saint's
particle glued to a name stays one word and is a name word, where 1.4
through 3.0 read ``St.John`` opening a name as a title and 2.4 through
3.0 read ``Sta.Ana`` ending one as a credential:

.. doctest::

    >>> glued = parse("Dr.John Smith")
    >>> glued.title, glued.given, str(glued)
    ('Dr.', 'John', 'Dr.John Smith')
    >>> parse("St.John Price").given, parse("Mark Jhon Sta.Ana").family
    ('St.John', 'Sta.Ana')

Commas and word dividers in other scripts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The commas of Ethiopic, Burmese, N'Ko, Mongolian, Manchu, Lisu, Vai and
Bamum divide a name as the ASCII comma does, and the Ethiopic wordspace
``፡`` divides its words, where 1.4 through 3.0 kept each inside the word
before it. The fullwidth full stop ``．`` between Han, Hangul or kana
names divides them as the middle dot does, where 1.4 through 3.0 read
one word. A narrow no-break space (U+202F) between two Mongolian
letters joins a case suffix to its word, where 1.4 through 3.0 divided
there:

.. doctest::

    >>> amharic = parse("ከበደ፣ አበበ")
    >>> amharic.family, amharic.given
    ('ከበደ', 'አበበ')
    >>> parse("አበበ፡ከበደ፡ተሰማ").middle
    'ከበደ'
    >>> taiwan = parse("台邦．撒沙勒")
    >>> taiwan.given, taiwan.family
    ('台邦', '撒沙勒')
    >>> parse("ᠬᠣᠷᠯᠤ᠎ᠠ ᠶ᠋ᠢᠨ ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ").middle
    ''

Dutch 't and 's
^^^^^^^^^^^^^^^

``'s`` before a surname is part of the family name, where 1.4 through
3.0 read it with the middle name, and neither ``'t`` nor ``'s`` is
reported as an unbalanced quote, as 2.0 through 3.0 reported it. A
nickname in quotes after ``'t`` is read as 1.4 read it, where 2.0
through 3.0 took the nickname from the ``'t``:

.. doctest::

    >>> gravesande = parse("Willem Jacob 's Gravesande")
    >>> gravesande.middle, gravesande.family, gravesande.ambiguities
    ('Jacob', "'s Gravesande", ())
    >>> parse("Jan van 't Hof 'Jantje'").nickname
    'Jantje'

Case repair: apostrophes, Georgian and hyphenated particles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Case repair keeps a Ukrainian or Belarusian apostrophe inside its word,
writes Georgian set in Mtavruli capitals in plain Mkhedruli, and
capitalizes a particle that opens a hyphenated word, save Dutch 's and
't, which keep their lowercase. 1.4 through 3.0 gave ``Мар'Яна``,
``Ნინო``, ``ter-Petrosyan`` and ``'S-Gravesande``:

.. doctest::

    >>> [str(parse(n).capitalized()) for n in ("БЕЗУГЛА МАР'ЯНА",
    ...     "ᲜᲘᲜᲝ ᲑᲣᲠᲯᲐᲜᲐᲫᲔ", "LEVON TER-PETROSYAN",
    ...     "WILLEM 'S-GRAVESANDE")]
    ["Безугла Мар'яна", 'ნინო ბურჯანაძე', 'Levon Ter-Petrosyan', "Willem 's-Gravesande"]

A Georgian name mixing Mtavruli with Mkhedruli is written in Mkhedruli
too, Georgian having no case that a capital sets against the rest of
the name, where 1.4 through 3.0 kept it as written; a Latin surname in
capitals in a name of mixed case is still kept:

.. doctest::

    >>> [str(parse(n).capitalized()) for n in ("ნინო ᲑᲣᲠᲯᲐᲜᲐᲫᲔ",
    ...     "Უჩა გოგოლაძე", "Jean DUPONT")]
    ['ნინო ბურჯანაძე', 'უჩა გოგოლაძე', 'Jean DUPONT']

A spaced ``Ter`` or ``Der`` opening the family name takes a capital too,
where 1.4 through 3.0 wrote it in lowercase; after another particle it
keeps its lowercase:

.. doctest::

    >>> [str(parse(n).capitalized()) for n in ("LEVON TER PETROSYAN",
    ...     "JAN VAN DER BERG")]
    ['Levon Ter Petrosyan', 'Jan van der Berg']

Initials in Thai and Burmese
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:meth:`~nameparser.ParsedName.initials` gives nothing for a word in
Thai or Burmese, scripts that shorten no name to a letter, as for Han,
Hangul and kana, where 1.4 through 3.0 gave its first character:

.. doctest::

    >>> [parse(n).initials() for n in ("สมชาย ใจดี", "ကြည် ကြည် ဌေး")]
    ['', '']

Transliteration digraphs
^^^^^^^^^^^^^^^^^^^^^^^^

A transliteration digraph opening a name, the Latin spelling of one
Cyrillic letter (``Yu.``, ``Ya.``, ``Ye.``, ``Yo.``, ``Zh.``, ``Kh.``,
``Shch.``, ``Dzh.``), is a given name where 1.4 through 3.0 read it as a
title. ``Ts.``, ``Ch.`` and ``Sh.``, each also a title written short,
are still titles, and other spellings of the same letters (the Library
of Congress ``Iu.``) are unchanged:

.. doctest::

    >>> digraph = parse("Yu. A. Chibrikova")
    >>> digraph.title, digraph.given, digraph.middle
    ('', 'Yu.', 'A.')
    >>> parse("Ts. Sandag-Ochir").title
    'Ts.'

``Md`` as a given name
^^^^^^^^^^^^^^^^^^^^^^

``Md.`` opening a name, Muhammad written short in Bangladesh and India,
is the given name, where 1.4 through 3.0 read it as a title; ``MD``
after a name is still the medical degree:

.. doctest::

    >>> short = parse("Md. Abdul Karim")
    >>> short.title, short.given, short.middle
    ('', 'Md.', 'Abdul')
    >>> parse("John Smith, MD").suffix
    'MD'

After a family comma ``Md`` opening the given part is the given name
too, where 1.4 through 2.5 read it as a title and 2.6 through 3.0 read
the part as credentials; ``MD`` in
capitals alone there is still the degree. To keep the 3.0 readings,
remove ``md``'s given reading (:ref:`customize-md-title`):

.. doctest::

    >>> karim = parse("Uddin, Md Karim")
    >>> karim.given, karim.middle, karim.suffix
    ('Md', 'Karim', '')
    >>> parse("UDDIN, MD").suffix
    'MD'

Maghrebi and Hebrew particles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``El``, ``Ait``, ``Aït``, ``Nait``, ``Ould`` and ``Ouled`` start the
family name they open, where 1.4 through 3.0 left them in the middle
name (``El`` opening a name stays the given name), and
``Ould`` fills ``patronymic``. So do Hebrew-script ``אבו`` and ``אל``;
``בן`` opening a name is the given name again, as in 1.4, where 2.0
through 3.0 read the name whole as the family, and inside a name it no
longer fills ``patronymic``:

.. doctest::

    >>> [parse(n).family for n in ("Youssef Ait Haddou",
    ...     "Ahmed Ould Haddou", "Sara El Haddou", "סאמי אבו חליל")]
    ['Ait Haddou', 'Ould Haddou', 'El Haddou', 'אבו חליל']
    >>> hebrew_ben = parse("בן כהן")
    >>> hebrew_ben.given, hebrew_ben.family
    ('בן', 'כהן')

A bound given name before ``El`` gives the rest to the family name,
where 2.2 through 3.0 read given ``Abd El`` and 1.4 through 2.1 middle
``El Kader``:

.. doctest::

    >>> abd_el = parse("Abd El Kader Haddou")
    >>> abd_el.given, abd_el.family
    ('Abd', 'El Kader Haddou')

More particles
^^^^^^^^^^^^^^

The standalone Arabic ``ال`` before a name, the clan prefix, and the
Icelandic ``frá``, "from", before a place name start the family name,
where 1.4 through 3.0 read them with the middle name. A particle's
family name runs on past a credential that spells a name (``Abd``,
``Md``), where 1.4 through 3.0 ended it there:

.. doctest::

    >>> [parse(n).family for n in ("سارة علي ال ناصر",
    ...     "Jónas Jónsson frá Hriflu", "Ahmad bin Abd Rahman")]
    ['ال ناصر', 'frá Hriflu', 'bin Abd Rahman']

Georgian, Armenian and Persian titles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Georgian and Armenian titles written in their own scripts, Persian
titles and the Persian spellings of the Arabic ones are titles, where
1.4 through 3.0 read them as the given name, and an Arabic word drawn
out with the tatweel ``ـ`` reads as it does without it. The Armenian
``Տեր`` opening a family name is part of it, and opening a name is a
priest's title:

.. doctest::

    >>> [parse(n).title for n in ("ბატონი დავით ყიფიანი",
    ...     "Պարոն Արամ Սարգսյան", "دکتر محمد رضایی", "الدكتــور خالد سالم")]
    ['ბატონი', 'Պարոն', 'دکتر', 'الدكتــور']
    >>> parse("Զավեն Տեր Եղիյան").family, parse("Տեր Հուսիկ Լազարյան").title
    ('Տեր Եղիյան', 'Տեր')

A Georgian name beside capitals
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A Georgian name is not read as mixed case beside a word in capitals,
Georgian's capitals making no case contrast, so ``MA`` after it is the
family name, as after an Arabic-script name, where 2.4 through 3.0 read
it as a credential:

.. doctest::

    >>> georgian_ma = parse("ჯეკ MA")
    >>> georgian_ma.family, georgian_ma.suffix
    ('MA', '')

Thai names
^^^^^^^^^^

Thai ranks, dotted salutations, academic and professional titles, and
salutations glued to the start of the given name are titles, where 1.4
through 3.0 read them as the given name or part of it. A Thai title
before one name word reads that word as the given name, where 1.4
through 3.0 read the family name, and a noble family name opening with
``ณ`` is one family name, where they read ``ณ`` as a middle name.
:ref:`thai-names` lists what is read:

.. doctest::

    >>> [(t.title, t.given) for t in map(parse, ("พ.ต.ท. สมมาตร เกลี้ยงสิน",
    ...     "นายสมชาย ใจดี", "รศ.ดร.สุดา ใจดี", "ดร. สุดา"))]
    [('พ.ต.ท.', 'สมมาตร'), ('นาย', 'สมชาย'), ('รศ.ดร.', 'สุดา'), ('ดร.', 'สุดา')]
    >>> parse("สุดา ณ อยุธยา").family
    'ณ อยุธยา'

Credentials joined at a full stop, and the Royal Colleges
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Listed credentials written in two chunks joined at a full stop
(``S.Pd``, ``M.Pd``, ``B.Pharm``) are credentials. After a comma, 1.4
through 2.3 read the first as a title and 2.4 through 3.0 read both as
one title; 2.4 through 3.0 also reported one ending a name as
``suffix-or-name``. The Royal Colleges' fellowships and
memberships (``FRCS``, ``MRCP``) are credentials, where 1.4 through 3.0
read them as the family or middle name:

.. doctest::

    >>> parse("Ayu Pangestu, S.Pd, M.Pd").suffix
    'S.Pd, M.Pd'
    >>> parse("Ahmed Ali B.Pharm").ambiguities
    ()
    >>> [parse(n).suffix for n in ("John Smith FRCS", "Smith, John MRCP")]
    ['FRCS', 'MRCP']

Title words at the ends of a name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A military title written short after a connective ends the name as a
title, where 3.0 read it with the family name. A title word between a
nickname and a suffix is the family name, where 2.3 through 3.0 read it
as the given name and 1.4 through 2.2 as a title:

.. doctest::

    >>> smith_maj = parse("John Smith y Maj.")
    >>> smith_maj.title, smith_maj.family
    ('Maj.', 'Smith y')
    >>> smitty = parse("'Smitty' Pope Jr.")
    >>> smitty.given, smitty.family
    ('', 'Pope')

Two capitals before a later credential
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Two capitals between a full name and credentials, after a comma, are a
credential, where 1.4 through 3.0 read them as the given name and the
whole name before the comma as the family name. They are read so beside
credentials in their own part, or alone in it before a listed
credential in a later one, where dotted initials are read so too.

Behind one word they are still the given name, as are two capitals
alone after the comma with no listed credential in a later part, and
dotted initials with credentials in their own part.
``Policy(unlisted_caps_suffixes=CapsSuffixes.OFF)`` keeps two
capitals the given name, with every other unlisted word in capitals
after a comma, and ``Policy(unlisted_dotted_suffixes=False)`` the
dotted ones:

.. doctest::

    >>> [(c.given, c.family, c.suffix) for c in map(parse, (
    ...     "Jane Doe, BM PhD", "Jane Doe, BM, PhD",
    ...     "Jane Doe, B.M., PhD"))]
    [('Jane', 'Doe', 'BM PhD'), ('Jane', 'Doe', 'BM, PhD'), ('Jane', 'Doe', 'B.M., PhD')]
    >>> [parse(n).given_names for n in ("Doe, BM, PhD", "Jane Doe, BM",
    ...     "Jane Doe, BM, Jr.", "Jane Doe, B.M. PhD")]
    ['BM', 'BM', 'BM', 'B.M.']

.. _migrate-3-1-initials-credential:

Initials that spell a credential
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dotted initials that spell a listed credential, after a comma and a
surname of one word, or of one word behind its particles (``de
Waart``), are the given and middle names, as the initials they may be,
where 2.0 through 3.0 read them as the credential
(:ref:`migrate-2-0`); 1.4 read them as one given name after a surname
of one word. The parse reports the credential it
did not read. Two name words before the comma, another credential in
the same part as the initials, or the undotted spelling keep the
credential:

.. doctest::

    >>> dotted = parse("Andrews, M.D.")
    >>> dotted.given, dotted.middle, dotted.suffix
    ('M.', 'D.', '')
    >>> [str(report.kind) for report in dotted.ambiguities]
    ['suffix-or-name']
    >>> parse("de Waart, M.D.").given, parse("de Waart, M.D.").family
    ('M.', 'de Waart')
    >>> [parse(n).suffix for n in ("Bin Zhang, M.D.",
    ...     "Andrews, M.D. Ph.D.", "Andrews, MD")]
    ['M.D.', 'M.D. Ph.D.', 'MD']

The order report
^^^^^^^^^^^^^^^^

A name of one word followed by initials reports an ``order`` ambiguity,
where 2.0 through 3.0 reported nothing; the reading is unchanged. The
report names no alternative, since the other reading lays out the whole
name (``name_order=FAMILY_FIRST`` reads it):

.. doctest::

    >>> kavitha = parse("Kavitha S")
    >>> [str(report.kind) for report in kavitha.ambiguities], kavitha.family
    (['order'], 'S')

.. _migrate-3-1-packs:

Under a pack or a setting
^^^^^^^^^^^^^^^^^^^^^^^^^

These move a reading only where a pack or a setting is chosen; the
default parse is unchanged:

- ``locales.TR_AZ`` reads a Kyrgyz name of three words ending in its
  patronymic marker with the family name ``Cholponbai uulu``, where 1.4
  (with Turkic handling) through 3.0 read ``uulu`` alone, and finds the
  Uzbek ``o‘g‘li`` written with a curly quote or a backtick, where 2.0
  through 3.0 read it as the family name.
- ``PatronymicRule.TURKIC`` finds a marker written with a combining mark
  (``oğlu`` with ``g`` and U+0306), where 2.0 through 3.0 did not.
- ``locales.RU`` keeps an initial before a surname ending like a
  patronymic in given-first order, where 2.0 through 3.0 rotated it.
- ``locales.ZH`` no longer divides a name opening with ``厐``
  (``厐建国``), which 2.5 through 3.0 divided; written ``龎`` it still
  divides.
- ``locales.MN`` is new, and reads a name written in Cyrillic father's
  name first; ``PolicyPatch.script_orders`` merges by script, where 2.1
  through 3.0 replaced the whole table.
- ``locales.AR`` and ``locales.HE`` are new, and read ``Ben`` inside a
  name as a family-name particle, where the default reads it as a middle
  name.

.. doctest::

    >>> import unicodedata
    >>> from nameparser import Parser, PatronymicRule, Policy, locales, parser_for
    >>> kyrgyz = parser_for(locales.TR_AZ).parse("Bekmyrza Cholponbai uulu")
    >>> kyrgyz.given, kyrgyz.family
    ('Bekmyrza', 'Cholponbai uulu')
    >>> parser_for(locales.TR_AZ).parse("Sa'dullayev Alisher Zafar o‘g‘li").family
    "Sa'dullayev"
    >>> turkic = Parser(policy=Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC})))
    >>> turkic.parse(unicodedata.normalize("NFD", "Mamedov Ali Huseyn oğlu")).family
    'Mamedov'
    >>> parser_for(locales.RU).parse("И. Б. Зубкевич").family
    'Зубкевич'
    >>> parser_for(locales.ZH).parse("厐建国").family
    '厐建国'
    >>> parser_for(locales.MN).parse("Батын Сүхээ").family
    'Батын'
    >>> parser_for(locales.AR).parse("Karim Ben Haddad").family
    'Ben Haddad'

``locales.JA`` lists the honorific ``君``, where 2.1 through 3.0 read it
with the given name, and ``ja_segmenter`` no longer cuts a name with no kanji
after its first character, where 2.1 through 3.0 did. The segmenter
needs the ``ja`` extra, and the pack warns without one, so the example
is not run here:

.. code-block:: python

    >>> parser_for(locales.JA).parse("逢沢　一郎君").suffix
    '君'
    >>> ja = parser_for(locales.JA, segmenter=locales.ja_segmenter())
    >>> ja.parse("あいさわいちろう").family
    'あいさわいちろう'

.. _migrate-3-2:

Changed in 3.2
~~~~~~~~~~~~~~

Each entry names the releases that read the name the old way.

Dutch Oude
^^^^^^^^^^

``Oude`` starts the family name it opens, where 1.4 through 3.1 left it
in the middle name, after a family comma too (``Luttikhuis, Piet
Oude``); opening a name it stays the given name, as before, and now
reports the fork, as ``van`` does:

.. doctest::

    >>> parse("Piet Oude Luttikhuis").family
    'Oude Luttikhuis'
    >>> oude_first = parse("Oude Luttikhuis")
    >>> oude_first.given, [str(report.kind) for report in oude_first.ambiguities]
    ('Oude', ['particle-or-given'])

``locales.NL``, new in 3.2, reads ``ten`` the same way (``Jan ten
Brink`` gives family ``ten Brink``); the default parse of a name holding
``ten`` is unchanged.

Malaysian a/l, a/p and anak
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``a/l`` (son of), ``a/p`` (daughter of) and ``anak`` (child of) start
the family name, the father's name, as ``bin`` does, where 1.4 through
3.1 left them in the middle name and cut a father's name of two words;
the ``patronymic`` view holds the same words. ``anak`` opening a name,
as Balinese ``Anak Agung`` does, stays the given name and reports the
fork:

.. doctest::

    >>> malaysian = parse("KUMAR A/L RAJAN NAIDU")
    >>> malaysian.middle, malaysian.family, malaysian.patronymic
    ('', 'A/L RAJAN NAIDU', 'A/L RAJAN NAIDU')
    >>> parse("Rita Sari anak Jerome Insol").family
    'anak Jerome Insol'
    >>> balinese = parse("Anak Agung Made Putra")
    >>> balinese.given, [str(report.kind) for report in balinese.ambiguities]
    ('Anak', ['particle-or-given'])
