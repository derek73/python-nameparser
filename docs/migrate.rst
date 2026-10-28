Migrating to 3.0
================

nameparser 3.0 removes the 1.x compatibility layer: ``HumanName``,
``Constants`` and everything around them, which 2.x kept working on top
of the core parser and 2.8 deprecated. This page is for code written
against either — 1.x code, and 2.x code that kept using ``HumanName``.
It says what is gone and what replaces each piece, then translates a
1.x customization or a 1.x-shaped comparison into the 3.0 API, one row
per old name.

The 3.0 API is the one 2.0 introduced — ``parse``, ``Parser``,
``Lexicon``, ``Policy``, ``Locale`` and ``ParsedName``, with
:mod:`nameparser.locales` — and its names and signatures carry into 3.0
gaining additions only. The vocabulary data modules in
``nameparser.config`` (``titles``, ``particles`` and the rest) stay.
Separately, the output model changes in 3.0; details with the 3.0
alphas.

The full 1.x documentation remains the reference for ``HumanName`` and
stays online as the 1.4.0 build on readthedocs:
https://nameparser.readthedocs.io/en/v1.4.0/

What 3.0 removes
----------------

2.8 warned at the line in your code that used each of these, with the
exceptions `Finding the sites`_ names:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Removed
     - Replacement
   * - ``HumanName(...)``, and the ``nameparser.parser`` module
     - ``nameparser.parse(text)``, or ``Parser(lexicon=...,
       policy=...).parse(text)``; the fields are ``given`` and
       ``family`` where ``HumanName`` has ``first`` and ``last``. See
       the `Attribute map`_
   * - ``Constants(...)``, ``constants.copy()`` and the shared
       ``CONSTANTS``
     - ``Parser(lexicon=Lexicon.default().add(titles={"dean"}))``, and
       the `Config map`_ for each setting
   * - ``SetManager``, ``TupleManager`` and ``RegexTupleManager`` in
       ``nameparser.config``
     - ``Lexicon`` fields take plain sets:
       ``Lexicon.default().add(titles={"dean"})``
   * - ``nameparser.util`` and its ``lc``
     - ``value.lower().strip(".")``
   * - Loading a pickled ``HumanName``
     - Store ``parse(text).as_dict()`` or the original string
   * - Loading a pickled ``Constants``
     - Pickle the ``Parser`` instead
   * - The 1.x names of five word lists and two of their modules,
       deprecated since 2.2
     - Their 2.2 names, which the 2.2.0 entry of :doc:`release_log`
       maps

The 2.8 deprecation warnings go with the code they warned about. In 3.0
importing a removed name raises ``ImportError``, reading one as an
attribute raises ``AttributeError``, and a pickle of a ``HumanName`` or
a ``Constants`` cannot load, because there is no class to load it into.

Finding the sites
~~~~~~~~~~~~~~~~~

Upgrade to 2.8 first. A ``DeprecationWarning`` is hidden by default
outside ``__main__``, so run your tests with warnings turned into
errors, and each use 3.0 removes stops the run at the line that makes
it:

.. code-block:: bash

    python -W error::DeprecationWarning -m pytest

2.8 warns where code *uses* a removed name, not where it imports one,
so some code passes that check and still fails on 3.0:

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

So search your code for ``CONSTANTS``, ``HumanName``, ``Constants``,
``nameparser.parser``, ``nameparser.util``, ``config.prefixes`` and
``config.bound_first_names`` as well.

Coming from 1.x
~~~~~~~~~~~~~~~

Code written against 1.4 meets 2.0's removals too, since 3.0 keeps
them. Most are moot now that ``HumanName`` and ``Constants`` are gone,
but three still reach code moving to ``parse()``:

* ``name == "John Smith"`` returned ``True`` on 1.x. ``HumanName``
  dropped ``__eq__`` in 2.0, silently, and a ``ParsedName`` compared to
  a string is never equal to it: use ``matches()`` (see `Comparison`_).
  Grep for ``==`` wherever you compare names
* bytes are not decoded for you: ``parse(b"...")`` raises
  ``TypeError``, so decode first (``raw.decode("utf-8")``)
* ``CONSTANTS.regexes.bidi = False``, 1.3.1's opt-out for keeping
  bidirectional marks, is ``Policy(strip_bidi=False)``, and the emoji
  one ``Policy(strip_emoji=False)`` (`Behavior and render settings →
  Policy`_)

Breaks in the 2.x core API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Later 2.x releases changed the core API in ways 3.0 keeps:

* editing a default word list in place — ``TITLES.add("dean")`` —
  raises ``AttributeError`` since 2.2, when the vocabulary sets became
  ``frozenset`` (see `Default word lists are frozen`_)
* a ``capitalization_exceptions`` value that is not a case mask of its
  key — ``{"md": "Doc"}`` — raises ``ValueError`` since 2.4
* a ``Lexicon``, ``Policy`` or ``Parser`` pickled by 2.5 or earlier
  raises ``ValueError`` on load since 2.6, each having gained a field;
  re-pickle after upgrading. A ``Lexicon``, ``Parser`` or locale pack
  pickled by 2.6 raises the same way since 2.7

Finally, if you want to see the difference on your own data rather than
ours, ``tools/differential/compare.py`` in the source repository diffs
any released version's parses against the source tree over the corpora
beside it, or over a file of your own names (``--corpus``). It is development
tooling, not part of the installed package — see its README.

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
     - The surname without its particles
   * - ``last_prefixes`` / ``last_prefixes_list``
     - ``family_particles``
     - The particles ``family_base`` was split from (e.g. ``"de la"``)
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
       active; passing the old scalar through raises
       (:ref:`suffix-delimiters`)
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

Config map
----------

Vocabulary sets → Lexicon
~~~~~~~~~~~~~~~~~~~~~~~~~

The vocabulary sets of a 1.x or 2.x ``Constants`` (and so of the shared
``CONSTANTS``) map onto :class:`~nameparser.Lexicon` fields:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - 1.x/2.x ``Constants``
     - 3.0 ``Lexicon``
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
     - Pair-valued, so not ``add()``/``remove()``; extend the defaults
       with ``dataclasses.replace()`` as :ref:`case-exceptions` shows.
       Since 2.4 a value is a case mask, so ``{"md": "M.D."}`` repairs
       ``md`` to ``MD``

Some ``Lexicon`` fields never had a ``Constants`` attribute —
``conjunctions_ambiguous``, ``maiden_markers``, ``surnames``,
``honorific_tails``, ``after_given_titles``, ``suffix_words_ambiguous``,
``agnomens`` and ``given_name_abbreviations`` — so code coming from
``Constants`` has nothing to translate for them.

.. warning::

   ``non_first_name_prefixes`` and ``particles_ambiguous`` mark
   **complementary** sets, not the same set under a new name.
   ``non_first_name_prefixes`` lists particles that are *never* read as
   a given name; ``particles_ambiguous`` lists the particles that
   *may* be read as one. The same holds for the config constant behind
   it: ``particles.NON_GIVEN_NAME_PARTICLES`` marks the never-given
   set, so it is the complement of ``particles_ambiguous`` too, however
   much the two names suggest otherwise. Translating a customization
   means flipping the set: ``particles_ambiguous = lexicon.particles -
   constants.non_first_name_prefixes``. Copying
   ``non_first_name_prefixes`` straight into ``particles_ambiguous``
   silently inverts which particles are allowed to double as a given
   name.

Default word lists are frozen
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every vocabulary *set* in ``nameparser.config`` is a ``frozenset``
as of 2.2. The freeze retires one 1.x
idiom outright: ``TITLES.add("dean")`` — editing a default word list
in place — raises ``AttributeError`` at the line that writes it.
``Lexicon.default()`` is cached and
reads the module constants once, at its first call, so an edit there
was never a dependable way to change a default: an edit made after the
first parse never reached it.

``CAPITALIZATION_EXCEPTIONS`` is the constant the freeze left out. It
is a mapping rather than a set, and it is still a plain mutable
``dict`` — ``CAPITALIZATION_EXCEPTIONS["dclinpsy"] = "DClinPsy"`` runs
and raises nothing — but the same caching applies: an edit after the
first parse is missed by ``Lexicon.default()``. Configure a
``Lexicon`` instead, with a ``dataclasses.replace()`` that extends the
default pairs rather than replacing them (:ref:`case-exceptions`).

To change a default word list, extend the default lexicon and hand it
to a parser:

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> parse("Dean Smith").given          # a title only in a phrase
    'Dean'
    >>> dean_parser = Parser(lexicon=Lexicon.default().add(titles={"dean"}))
    >>> dean_parser.parse("Dean Smith").title
    'Dean'

See :doc:`customize` for the full set of knobs.

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
       ``(open, close)`` pairs. The defaults gained the #273
       typographic pairs (smart quotes, guillemets, CJK brackets, ...)
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
handing the parser a regex.

Comparison
----------

``HumanName.__eq__``/``__hash__`` were deprecated in 1.3.0 and removed
in 2.0, and 3.0 has no ``HumanName`` at all. A
:class:`~nameparser.ParsedName` is never equal to a string, so use
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

Behavior changes
-----------------

Beyond the API surface mapped above, a handful of parse *outputs*
differ between 1.4 and 3.0 for specific input shapes. The full list,
with reasoning, is in each 2.x section of :doc:`release_log`.

Changed in 2.0
~~~~~~~~~~~~~~

These are the shapes worth grepping your own fixtures for, because a
recognized suffix or title now stays in its own field instead of
landing in the given or family name:

.. doctest::

    >>> parse("Andrews, M.D.").family, parse("Andrews, M.D.").suffix
    ('Andrews', 'M.D.')
    >>> parse("Johnson PhD").given, parse("Johnson PhD").suffix
    ('Johnson', 'PhD')

Under 1.4 those read ``first="M.D."``/``last="Andrews"`` and
``first="Johnson"``/``last="PhD"`` respectively. Two more to check for:
a maiden marker now fills the ``maiden`` field rather than being folded
into the middle or family name (``"Jane Smith née Jones"``), and with a
custom suffix delimiter configured, a no-space delimiter group renders
whole (``"RN/CRNA"``) where 1.x split it (``"RN, CRNA"``) — the role
assignment is identical, only the rendered string differs.

East Asian names (2.1)
~~~~~~~~~~~~~~~~~~~~~~

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
second whole in ``first``. The Korean one also changes what the name
*renders* as — ``str(parse("김민준"))`` is ``"민준 김"``, where 1.4's
``str(HumanName("김민준"))`` was ``"김민준"`` — because the split
inserts a token boundary that the default format then writes
given-name-first.

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
``first``. The spaced shapes change what the name renders as too:
``str(parse("高橋 みなみ"))`` is ``"みなみ 高橋"``, where 1.4 wrote
``"高橋 みなみ"``. A name written *wholly* in katakana is deliberately
left alone — it may be a transcribed foreign name already in
given-first order or a Japanese name's reading written family-first,
and the script cannot tell which (see :ref:`east-asian-names` to opt
in) — so ``parse("マイケル ジャクソン")`` reads given ``マイケル``,
family ``ジャクソン``, as 1.4 did.

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
family-first rule. Separating also changes the rendered string, the
same way the Korean split does: the dot comes back as a space, so
``str(parse("マイケル・ジャクソン"))`` is ``"マイケル ジャクソン"``,
where 1.4 wrote ``"マイケル・ジャクソン"``. That reaches delimited content
too — the nickname in ``"山田 太郎 (マイケル・ジャクソン)"`` was
``"マイケル・ジャクソン"`` under 1.4 and is ``"マイケル ジャクソン"``
now.

Turning the East Asian readings off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The switch is on the ``Policy`` (:ref:`east-asian-defaults`):
``Parser(policy=Policy(script_orders=(), segment_scripts=frozenset()))``
restores 1.4's reading of every shape above that turns on order or
splitting. The middle dots are the exception: both the katakana dot
and the Chinese interpunct ``·`` (U+00B7, dividing a transcription
like ``威廉·莎士比亚``, and a separator only between classified-script
characters — each side judged on its own — where the katakana dot is
unconditional) are decided
in tokenization rather than by policy, so a name written with either
still divides at the dot, and still renders with a space, whatever
those two fields are set to.

Changed in 2.3 through 2.8
~~~~~~~~~~~~~~~~~~~~~~~~~~

Later releases moved more 1.4 readings; 2.1 and 2.2 read every one of
them as 1.4 did. The release
log's 2.3 to 2.8 sections carry the reasoning; these are the shapes to
grep your fixtures for, with what 1.4 read:

- ``"Her Majesty Queen Elizabeth"``, ``"His Royal Highness Prince Harry"`` (2.3) — a lone
  name after a title that addresses by given name is the given name:
  1.4 read last ``Elizabeth`` and ``Harry``. 2.3 matched a run of titles
  by its last one (``Her Majesty Queen``, ``Rev Sir``) and added titles
  that address that way (``Prince``, ``Princess``, ``Swami``, ``Guru``
  and others). Other titles still leave the name the family name
  (``"Dr Harry"``). Since 2.7 a bare ``Prince`` or ``Princess`` is a
  given name (below); behind a style, as here, it is still a title.
- ``"Dr King Jr"`` (2.3) — 1.4 read title ``Dr King``, last ``Jr``.
- ``"John Smith Prof."`` (2.3) — a trailing period-marked title: 1.4
  read last ``Prof.``, middle ``Smith``.
- ``"Jack MA"`` (2.4) — an ambiguous acronym in capitals in a mixed-case
  name is a credential: 1.4 read last ``MA``. ``"Jack Ma"`` and
  ``"JACK MA"`` are unchanged.
- ``"jose e maria santos"`` (2.4) — ``e`` in a name written wholly in
  one case is an initial (``y`` still joins): 1.4 read first ``jose e
  maria``.
- ``"van der Berg, PhD"`` (2.4) — 1.4 read first ``van``, last ``der
  Berg``.
- ``"Josep Carod i Rovira"`` (2.4) — ``i`` links two surnames in a
  mixed-case name: 1.4 read middle ``Carod i``, last ``Rovira``.
- ``"Jane Smith N.C.C."`` (2.4) — an unlisted dotted credential after a
  full name: 1.4 read last ``N.C.C.``, middle ``Smith``. ``"Jack
  X.Y.Z."`` is unchanged.
- ``"Jane Smith, LEED AP"`` (2.4) — an unlisted all-caps credential
  after a comma: 1.4 read first ``LEED``, middle ``AP``, last ``Jane
  Smith``.
- ``"Eric H. Holder Jr. Attorney General"`` and ``"Eric H. Holder, Jr.,
  Attorney General"`` (2.4) — a title after a credential is a title:
  1.4 read middle ``H. Holder Jr. Attorney``, last ``General``, and
  suffix ``Jr., Attorney General``.
- ``"Steven Hardman, RN - CRNA"`` (2.4) — a credential after a comma
  starts a run of credentials, and since 2.7 the hyphen standing alone
  parts it as a comma (suffix ``RN, CRNA``): 1.4 read first ``RN``,
  middle ``-``, last ``Steven Hardman``, suffix ``CRNA``.
- ``"John van der Berg Prof."`` (2.4) — 1.4 read last ``van der Berg
  Prof.``.
- ``"Liam Ó Murchú"`` (2.4) — the Irish particles ``Ó``, ``Ní`` and
  ``Ua`` join the surname: 1.4 read middle ``Ó``, last ``Murchú``.
- ``"Herra Väinö Johansson"`` (2.4) — salutations in Finnish,
  Icelandic, Malay and other languages are titles: 1.4 read first
  ``Herra``, middle ``Väinö``.
- ``"山田 ﾀﾛｳ"`` (2.4) — halfwidth katakana reads as katakana: 1.4 read
  first ``山田``, last ``ﾀﾛｳ``.
- capitalizing ``"john smith md"``, ``"john smith phd"`` and
  ``"JANE DOE MBA"`` (2.4) — 1.4 wrote ``M.D.``, ``Ph.D.`` and ``Mba``;
  credentials are now written the usual way (``MD``, ``PhD``, ``MBA``).
- ``initials()`` on ``"john e smith"`` (2.4) — 1.4 gave ``j. s.``; a
  one-letter connective read as an initial now contributes one.
- ``"Dr. Smith, John"`` (2.5) — a listed title before a family comma is
  a title: 1.4 read last ``Dr. Smith``. ``"Gov Smith"`` (2.5) — ``Gov``
  is a title: 1.4 read first ``Gov``.
- ``"Antonio Pavlović mlađi"`` (2.5) — junior and senior in 45
  languages are suffixes: 1.4 read middle ``Pavlović``, last ``mlađi``.
- ``"John Smith II, AD"`` (2.5) — a credential after a generational
  suffix and a comma: 1.4 read first ``AD``, last ``John Smith``.
- ``"John III, Sir"`` and ``"Smith, Sir"`` (2.5) — the name before
  a comma and a given-name title is the given name: 1.4 read last
  ``John`` and ``Smith``.
- ``"Ivoi, Paul d'"`` (2.5) — a particle after the given name joins the
  surname: 1.4 read middle ``d'``.
- ``"jose j y lopez"`` (2.5) — a lone letter in a one-case name reads as
  in capitals: 1.4 read last ``j y lopez``.
- ``"Bapak Dwi Putro"`` (2.5) — the salutations ``bapak`` and ``owura``
  are titles: 1.4 read first ``Bapak``, middle ``Dwi``.
- capitalizing ``"jacobus henricus van 't hoff"`` (2.5) — 1.4
  wrote ``van 'T Hoff``.
- ``"Maria de Sa"`` and ``"John Smith SA"`` (2.6) — ``Sa`` is no longer
  a credential: 1.4 read last ``de``, suffix ``Sa``, and suffix ``SA``.
- ``"Cllr John Smith"`` and ``"Dott.ssa Anna Bianchi"`` (2.6) — ``Cllr``
  and the Italian abbreviated salutations are titles: 1.4 read first
  ``Cllr`` and ``Dott.ssa``, middle ``John`` and ``Anna``.
- ``"José Silva Júnior"`` (2.6) — 1.4 read middle ``Silva``, last
  ``Júnior``.
- ``"John Smith, MD; PhD"`` (2.6) — a semicolon between post-nominals
  reads as a comma: 1.4 read first ``MD;``, last ``John Smith``.
- ``"Mr Md Karim Uddin"`` and ``"Wm Smith"`` (2.6) — ``Md`` and ``Wm``
  are the given names they abbreviate: 1.4 read title ``Mr Md`` and
  ``Wm``.
- ``"Doe, Jane Mrs"`` (2.6) — a salutation ending the given name after a
  family comma is the title: 1.4 read middle ``Mrs``.
- A zero-width space or byte-order mark (2.6) divides words as a space
  does: 1.4 kept it in the word beside it, so ``"\u200bDr. John Smith"``
  read first ``Dr.``.
- capitalizing ``"j.r.r. tolkien"`` (2.6) — 1.4 wrote ``J.r.r.``;
  repair now capitalizes after a full stop or an ayn.
- ``"King Curtis"``, ``"Prince Fielder"``, ``"Sultan Khan"`` and
  ``"Sheikh Ahmed Khan"`` (2.7) — a title that is also a given name is a
  title only inside a title phrase or behind a style (``"His Majesty
  King Henry"``), so a bare one opening the name is the first name: 1.4
  read title ``King``, ``Prince``, ``Sultan`` and ``Sheikh``. The same
  holds for ``Princess``, ``Sultana``, ``Shaikh``, ``Sheik``, ``Shekh``,
  ``Shaik``, ``Cheikh``, ``Mahdi``, ``Bard``, ``Buddha``, ``Siddha``,
  ``Gyani`` and ``Wing``, and for a lone qualifier such as ``Grand``.
  ``Lexicon.default().add(titles={"king"})`` makes one a title
  everywhere.
- ``"Chief Justice John Roberts"`` and ``"Major General John Smith"``
  (2.7) — a title phrase is one title: 1.4 read title ``Chief``, first
  ``Justice``, and first ``Major``, middle ``General John``.
- ``"Chas. Smith"`` and ``"Ma. Cristina Reyes"`` (2.7) — a given name
  written short is the first name: 1.4 read title ``Chas.`` and ``Ma.``.
- ``"John Smith VI MD"`` and ``"Smith, John VI"`` (2.7) — the numerals
  ``VI`` to ``X`` are suffixes as ``III`` is: 1.4 read last ``VI``,
  suffix ``MD``, and middle ``VI``.
- ``"John Smith, MD/PhD"`` and ``"John Smith, Pharm D"`` (2.7) — a
  credential joined by a hyphen or slash, or split by a space, after a
  comma is a suffix: 1.4 read first ``MD/PhD``, and first ``Pharm``,
  middle ``D``, each with last ``John Smith``.
- ``"John Smith Ph. D. Jones"`` (2.7) — 1.4 read last ``Jones``, suffix
  ``Ph. D.``.
- ``"Smith, John MA Jones"`` (2.7) — a listed credential in capitals in
  a mixed-case name starts the suffix: 1.4 read middle ``Jones``, suffix
  ``MA``.
- ``"Pedro Alves Filho"`` and ``"Alexandre Dumas fils"`` (2.7) — the
  Brazilian agnomens and ``fils`` are suffixes where the name has a word
  to spare: 1.4 read middle ``Alves`` and ``Dumas``, last ``Filho`` and
  ``fils``.
- ``"Andrew Perkins (JD)"`` (2.7) — a bracketed credential its writing
  settles is a suffix: 1.4 read nickname ``JD``.
- ``"Jane Smith, Dr. / MD"`` (2.7) — a hyphen or slash standing alone
  between post-nominals reads as a comma: 1.4 read first ``/``, last
  ``Jane Smith``.
- ``"Marie Bon Durand"`` and ``"Herren Hans"`` (2.7) — ``Bon``, ``Dí``
  and ``Heer`` are no longer particles, nor ``Herren`` and ``Heren``
  titles: 1.4 read last ``Bon Durand`` and title ``Herren``.
- ``"Marquis Johnson"`` and ``"Johnson, Marquise"`` (2.8) — ``Marquis``
  and ``Marquise`` are titles only inside a title phrase, as ``King`` is
  since 2.7 (``"Marquis of Queensberry"`` keeps the title): 1.4 read
  title ``Marquis`` and ``Marquise``.
- ``"Deacon Jones"``, ``"Burgess Meredith"`` and ``"Ranger Smith"``
  (2.8) — ``Deacon``, ``Burgess`` and ``Ranger`` are titles only inside a
  title phrase, as ``King`` is since 2.7 (``"Deacon of the Church Jane
  Smith"`` keeps the title): 1.4 read title ``Deacon``, ``Burgess`` and
  ``Ranger``.
- ``"Queen Latifah"`` and ``"Elizabeth II, Queen"`` (2.8) — ``Queen`` is
  a title only inside a title phrase or behind a style (``"Her Majesty
  Queen Elizabeth"``), as ``King`` is since 2.7: 1.4 read title
  ``Queen``, first ``Latifah``, and last ``Elizabeth``.
- ``"Prince Consort Albert"``, ``"Princess Royal Anne"`` and ``"Bales,
  Royal"`` (2.8) — the royal title phrases are one title, and ``Royal``
  after a family comma is the first name: 1.4 read title ``Prince``,
  first ``Consort``; title ``Princess Royal``, last ``Anne``; and title
  ``Royal``, first ``Bales``.
- ``"Chancellor Smith"`` and ``"Lord Justice Leveson"`` (2.8) —
  ``Chancellor`` is a title only inside a title phrase (``"Lord
  Chancellor John Smith"``), and ``Lord Justice`` and ``Lady Justice`` are
  one title: 1.4 read title ``Chancellor``, and title ``Lord``, first
  ``Justice``.

.. doctest::

    >>> parse("Jack MA").suffix
    'MA'
    >>> parse("Her Majesty Queen Elizabeth").given
    'Elizabeth'
    >>> parse("His Royal Highness Prince Harry").given
    'Harry'
    >>> king = parse("Dr King Jr")
    >>> king.title, king.family, king.suffix
    ('Dr', 'King', 'Jr')
    >>> parse("John Smith Prof.").title
    'Prof.'
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
