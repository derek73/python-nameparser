Migrating from HumanName
=========================

``HumanName`` and ``CONSTANTS`` keep working in 2.0 — same imports,
same attributes, same mutation API (``name.C.titles.add(...)``,
``name.first = "..."``, and so on). Upgrading to 2.0 and migrating your
code to the new :class:`~nameparser.Parser`/:class:`~nameparser.Lexicon`/
:class:`~nameparser.Policy` API are two separate decisions — you can do
the former today and the latter whenever it's convenient. The
compatibility layer (``HumanName``, ``Constants`` and the shared
``CONSTANTS``) is removed in 3.0, and 2.8 warns wherever your code
touches it: see `Deprecated in 2.8`_. The vocabulary data modules in
``nameparser.config`` (``titles``, ``particles`` and the rest) stay.

The full 1.x documentation remains the canonical reference for
``HumanName`` and stays online as the 1.4.0 build on readthedocs:
https://nameparser.readthedocs.io/en/v1.4.0/

This page exists for the other direction: translating a v1
customization or a v1-shaped comparison into the 2.0 API, one row per
old name.

Deprecated in 2.8
-----------------

nameparser 2.8 is the last 2.x feature release. From 2.8 on, the uses
3.0 removes emit a ``DeprecationWarning`` at the line in your code that
makes them, on every call rather than once per process:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - What warns
     - Replacement
   * - ``HumanName(...)``, including a subclass's construction
     - ``nameparser.parse(text)``, or ``Parser(lexicon=...,
       policy=...).parse(text)``; the fields are ``given`` and
       ``family`` where ``HumanName`` has ``first`` and ``last``. See
       the `Attribute map`_
   * - ``Constants(...)`` and ``constants.copy()``
     - ``Parser(lexicon=Lexicon.default().add(titles={"dean"}))``, and
       the `Config map`_ for each setting
   * - Mutating the shared ``CONSTANTS`` (warned since 2.0)
     - The same ``Parser``; a private ``Constants`` is no longer a
       way out, since it goes in 3.0 too
   * - Loading a pickled ``HumanName``
     - Store ``parse(text).as_dict()`` or the original string
   * - Loading a pickled ``Constants``
     - Pickle the ``Parser`` instead
   * - Reading ``SetManager``, ``TupleManager`` or ``RegexTupleManager``
       from ``nameparser.config``
     - ``Lexicon`` fields take plain sets:
       ``Lexicon.default().add(titles={"dean"})``
   * - Reading ``lc`` from ``nameparser.util``
     - ``value.lower().strip(".")``

Importing ``nameparser``, ``nameparser.parser`` or ``HumanName`` stays
quiet, and so does ``from nameparser import *``; the warning comes when
the code runs. ``from nameparser.config import *`` does warn, once for
each manager it imports, and so does ``from nameparser.util import *``. One use does not warn: *reading* the shared ``CONSTANTS``
(``"dr" in CONSTANTS.titles``, or ``copy.copy(CONSTANTS)``), which
stays quiet so that importing ``nameparser`` does. Search your code for ``CONSTANTS`` as well. A
``DeprecationWarning`` is hidden by default outside ``__main__``, so
run your tests to see the rest, or turn them into errors to find each
site:

.. code-block:: bash

    python -W error::DeprecationWarning -m pytest

The 2.0 API's names and signatures carry into 3.0, gaining additions
only: ``parse``, ``Parser``, ``Lexicon``, ``Policy``, ``Locale`` and
``ParsedName``. Separately, the output model changes in 3.0; details
with the 3.0 alphas.

Before you upgrade
------------------

What breaks without a warning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What 2.0 removes is the batch of deprecations 1.3 and 1.4 announced. If
your test suite runs clean on 1.4 under ``python -W
error::DeprecationWarning``, it will run on 2.0.0 — with the exceptions
below, which 1.4 never warned about. The first three raise the first
time you hit them; the last only warns, so read it carefully:

* ``CONSTANTS.regexes.<name> = ...`` raises ``TypeError``. This includes
  ``CONSTANTS.regexes.bidi = False``, the opt-out 1.3.1 recommended for
  keeping bidirectional marks; the 2.0 spellings are
  ``Policy(strip_bidi=False)`` and ``Policy(strip_emoji=False)``
* assigning a ``*_list`` attribute (``name.first_list = [...]``) raises
  ``AttributeError`` — the lists are read-only snapshots in 2.0
* positional ``Constants(...)`` construction raises ``TypeError``; the
  constructor is keyword-only
* a subclass overriding a v1 parsing hook (``pre_process``,
  ``parse_pieces``, ``is_title``, and the rest) gets a
  ``DeprecationWarning`` at construction naming the hooks it overrode,
  because 2.0 delegates parsing to the core parser and never calls them

Later 2.x releases add breaks of their own, none of which 1.4 warned
about either:

* editing a default word list in place — ``TITLES.add("dean")`` —
  raises ``AttributeError`` since 2.2, when the vocabulary sets became
  ``frozenset`` (see `Default word lists are frozen`_)
* reading a renamed config constant (``prefixes.PREFIXES`` and the
  rest) emits a ``DeprecationWarning`` since 2.2, which fails a suite
  run under ``-W error::DeprecationWarning``
* a ``capitalization_exceptions`` value that is not a case mask of its
  key — ``{"md": "Doc"}`` — raises ``ValueError`` at the first parse
  since 2.4
* a ``Constants`` entry no word can match — empty, only full stops, or
  holding whitespace no word carries, in a vocabulary set or as a
  ``capitalization_exceptions`` key — is dropped with a ``UserWarning``
  naming it, since 2.4
* a ``Lexicon``, ``Policy`` or ``Parser`` pickled by 2.5 or earlier
  raises ``ValueError`` on load since 2.6, each having gained a field;
  re-pickle after upgrading. A ``Lexicon``, ``Parser`` or locale pack
  pickled by 2.6 raises the same way since 2.7

A silent change: comparing with ``==``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One removal changes results without saying anything. ``HumanName`` no
longer defines ``__eq__``, so ``name == "John Smith"`` is now ``False``
where 1.x returned ``True``. That one *did* warn on 1.4, but nothing
will tell you on 2.0. If you compare names anywhere, grep for ``==``
before upgrading and move to ``matches()`` — see `Comparison`_.

Re-pickle before you upgrade
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One step has to happen *before* you upgrade, because the fix is only
available on the version you're leaving: a ``Constants`` pickle written
by nameparser 1.2.x or earlier must be re-pickled under 1.3 or 1.4.
2.0 refuses to load one, and by then the code that could rewrite it is
gone.

Replacements for the warned removals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your suite did *not* run clean, these are the replacements for the
warned removals:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - 1.4 spelling
     - 2.0 replacement
   * - ``HumanName(b"...")``, ``manager.add(b"...")``
     - Decode first: ``HumanName(raw.decode("utf-8"))``
   * - ``SetManager.add_with_encoding(b"...")``
     - ``add()``, on already-decoded ``str``
   * - ``manager()`` (calling a set manager)
     - ``set(manager)``, or iterate it directly
   * - ``manager.remove(missing)`` (was tolerant)
     - ``discard()`` to ignore missing; ``remove()`` now raises
       ``KeyError`` like ``set.remove``
   * - ``HumanName(..., constants=None)``
     - ``Constants()`` for library defaults, or ``CONSTANTS.copy()``
       for a private snapshot of the current shared config (both
       deprecated since 2.8: see `Deprecated in 2.8`_)
   * - ``name['first'] = value``
     - ``name.first = value``
   * - ``CONSTANTS.regexes.typo`` (returned ``EMPTY_REGEX``)
     - ``.get("typo")`` for intentional soft access; attribute access
       now raises ``AttributeError``. The same applies to
       ``capitalization_exceptions``, whose error also lists the known
       keys
   * - ``CONSTANTS.empty_attribute_default``
     - Gone; empty fields are always ``''``

Finally, if you want to see the difference on your own data rather than
ours, ``tools/differential/compare.py`` in the source repository diffs
any released version's parses against the source tree over the corpora
beside it, or over a file of your own names (``--corpus``). It is development
tooling, not part of the installed package — see its README.

Attribute map
-------------

``HumanName``'s seven fields and their aggregates map onto
:class:`~nameparser.ParsedName` like this:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - ``HumanName``
     - ``ParsedName``
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
     - Unchanged name; ``middle`` folded into ``first``
   * - ``surnames`` / ``surnames_list``
     - ``surnames``
     - Unchanged name; ``middle`` folded into ``last``
   * - ``last_base`` / ``last_base_list``
     - ``family_base``
     - The surname with leading particles split off
   * - ``last_prefixes`` / ``last_prefixes_list``
     - ``family_particles``
     - The particles ``family_base`` was split from (e.g. ``"de la"``)
   * - ``string_format``
     - ``render(spec)``
     - A per-call argument now, not stored config — see
       :ref:`rendering-arguments`
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
     - The keys are the 2.0 field names
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

Side by side:

.. doctest::

    >>> from nameparser import HumanName, parse, Role
    >>> hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
    >>> n = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> hn.title == n.title, hn.first == n.given, hn.last == n.family
    (True, True, True)
    >>> hn.first_list == [t.text for t in n.tokens_for(Role.GIVEN)]
    True
    >>> hn.given_names == n.given_names, hn.surnames == n.surnames
    (True, True)
    >>> hn.last_base == n.family_base, hn.last_prefixes == n.family_particles
    (True, True)

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

``CONSTANTS``' vocabulary sets map onto :class:`~nameparser.Lexicon`
fields:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - ``CONSTANTS``
     - ``Lexicon``
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

Some ``Lexicon`` fields have no ``CONSTANTS`` attribute at all —
``conjunctions_ambiguous``, ``maiden_markers``, ``surnames``,
``honorific_tails``, ``after_given_titles``, ``suffix_words_ambiguous``,
``agnomens`` and ``given_name_abbreviations`` — so they are reached
through the 2.0 API only.

.. warning::

   ``non_first_name_prefixes`` and ``particles_ambiguous`` mark
   **complementary** sets, not the same set under a new name.
   ``non_first_name_prefixes`` lists particles that are *never* read as
   a given name; ``particles_ambiguous`` lists the particles that
   *may* be read as one. The same holds for the config constant behind
   it (renamed in 2.2; see `Renamed word lists (2.2)`_ below):
   ``particles.NON_GIVEN_NAME_PARTICLES`` (1.x
   ``prefixes.NON_FIRST_NAME_PREFIXES``) marks the never-given set, so
   it is the complement of ``particles_ambiguous`` too, however much
   the 2.2 names now suggest otherwise. Translating a customization
   means flipping
   the set: ``particles_ambiguous = lexicon.particles -
   constants.non_first_name_prefixes``. Copying
   ``non_first_name_prefixes`` straight into ``particles_ambiguous``
   silently inverts which particles are allowed to double as a given
   name.

Renamed word lists (2.2)
~~~~~~~~~~~~~~~~~~~~~~~~

The vocabulary that feeds both columns is exposed by ``nameparser.config``
(compiled since 2.6 from ``nameparser/vocab/*.toml``, all but the Korean
surname list),
and in 2.2 its module and constant names moved to the vocabulary the
``Lexicon`` column speaks — particles, bound given names, given-name
titles, suffix words. Terminology only; one of the four kept 1.x's
*meaning* while its ``Lexicon`` counterpart marks the opposite set, so
read the caveat under the table before pairing them up. If you import
the default word lists directly — to read one, extend one, or copy one
into your own configuration — four vocabularies moved:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - 1.x name
     - 2.2 name
   * - ``nameparser.config.prefixes``
     - :mod:`nameparser.config.particles`
   * - ``prefixes.PREFIXES``
     - ``particles.PARTICLES``
   * - ``prefixes.NON_FIRST_NAME_PREFIXES``
     - ``particles.NON_GIVEN_NAME_PARTICLES``
   * - ``nameparser.config.bound_first_names``
     - :mod:`nameparser.config.bound_given_names`
   * - ``bound_first_names.BOUND_FIRST_NAMES``
     - ``bound_given_names.BOUND_GIVEN_NAMES``
   * - ``titles.FIRST_NAME_TITLES``
     - ``titles.GIVEN_NAME_TITLES``
   * - ``suffixes.SUFFIX_NOT_ACRONYMS``
     - ``suffixes.SUFFIX_WORDS``

The caveat is on the third row. ``NON_GIVEN_NAME_PARTICLES`` is
``NON_FIRST_NAME_PREFIXES`` renamed and nothing else — same members,
same *never a given name* meaning. It is **not** the constant behind
``Lexicon.particles_ambiguous``, which is that field's complement, even
though the two now sound as though they belong together. Pairing this
table's third row with the field-mapping table above and concluding
that ``NON_GIVEN_NAME_PARTICLES`` is what ``particles_ambiguous``
holds is exactly the inversion the flip warning above exists to
prevent.

Every row still resolves, and the old names are removed in 3.0. The two
module rows are import paths and nothing more: importing
``nameparser.config.prefixes`` or ``nameparser.config.bound_first_names``
still works and says nothing, because the modules are now empty shims.
It is reading a *constant* that reports — by attribute access, by
``from ... import``, and by ``from ... import *`` alike. The read emits
a ``DeprecationWarning`` naming the module and constant to move to,
then returns the constant from its new home.

The warning fires once per line that reads a retired name, not once per
process, so a repeated read of the same import stays quiet while a
second import somewhere else in your code reports for itself. To find
your own uses, raise ``DeprecationWarning`` — which Python hides by
default outside ``__main__``, so an untouched run of a library that
reads these names on import shows nothing::

    python -W error::DeprecationWarning -c "import yourapp"

That stops at the first one, with a traceback whose last frame outside
nameparser is the line to edit. Swap ``error`` for ``default`` to print
them all and keep going.

Only the data layer moved: the ``CONSTANTS`` attribute names in the
field-mapping table above are v1 facade surface and are unaffected,
so ``constants.prefixes``,
``constants.non_first_name_prefixes``, ``constants.bound_first_names``,
``constants.first_name_titles`` and ``constants.suffix_not_acronyms``
keep their 1.x spelling for as long as the facade exists.

Default word lists are frozen
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every vocabulary *set* in ``nameparser.config`` is also a ``frozenset``
as of 2.2 — the renamed ones and the rest. Every set, that is; the one
mapping constant is untouched, and there is a note on it below. The
freeze retires one 1.x idiom outright: ``TITLES.add("dean")`` — editing
a default word list in place — now raises ``AttributeError`` at the
line that writes it, rather than changing some parses and not others
some distance away.

It was never a dependable way to change a default, because the two
config layers read the module constants at different moments.
``Lexicon.default()`` is cached and reads them exactly once, at its
first call; a v1 ``Constants`` copies them at every construction; and
the shared ``CONSTANTS`` singleton is one such copy, taken at import.
An edit landing *after* the first parse therefore reached only a
freshly built ``Constants`` — neither ``parse()``, whose lexicon was
already built, nor the shared ``CONSTANTS``, which predated the edit.
An edit landing *before* any parse reached ``Lexicon.default()``, and
so ``parse()``, and a fresh ``Constants`` — but still never the shared
``CONSTANTS``. Whether an edit reached a given parse thus depended on
which config objects the program had already built, and one program
could hold two disagreeing defaults with nothing to say so.

``CAPITALIZATION_EXCEPTIONS`` is the constant the freeze left out. It
is a mapping rather than a set, and it is still a plain mutable
``dict`` — ``CAPITALIZATION_EXCEPTIONS["dclinpsy"] = "DClinPsy"`` runs on 2.2 and
raises nothing. Everything just said about split defaults still applies
to it, unchanged and measured on 2.2 and again on 2.6: an edit after the first parse
reaches a freshly built ``Constants``, and neither
``Lexicon.default()`` nor the shared ``CONSTANTS``. The advice below is
the same advice — configure the object, with
``constants.capitalization_exceptions["dclinpsy"] = "DClinPsy"`` on a private
``Constants``, or for the 2.0 API a ``dataclasses.replace()`` that
extends the default pairs rather than replacing them
(:ref:`case-exceptions`).

Configure the objects instead, which both APIs have always supported
and neither the freeze nor the rename affects. For ``HumanName``, build
a private ``Constants`` and pass it:

.. doctest::

    >>> from nameparser import HumanName
    >>> from nameparser.config import Constants
    >>> HumanName("Dean Smith").first      # a title only in a phrase
    'Dean'
    >>> dean_constants = Constants()
    >>> _ = dean_constants.titles.add("dean")    # returns the set
    >>> HumanName("Dean Smith", constants=dean_constants).title
    'Dean'

For the 2.0 API, extend the default lexicon and hand it to a parser:

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> dean_parser = Parser(lexicon=Lexicon.default().add(titles={"dean"}))
    >>> dean_parser.parse("Dean Smith").title
    'Dean'

Mutating the shared ``CONSTANTS`` singleton still works and still
reaches every ``HumanName`` that reads it, but it warns: it is
deprecated along with the rest of the v1 facade and goes away in 3.0.
Since 2.8 a private ``Constants`` warns at construction too, so new
code should build the ``Parser``. See :doc:`customize` for the full
set of knobs on each.

Behavior and render settings → Policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Behavior and render scalars map onto :class:`~nameparser.Policy` (or a
rendering argument, where the 2.0 equivalent isn't config at all):

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - ``CONSTANTS``
     - 2.0 equivalent
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
       ``(open, close)`` pairs. Both APIs gained the #273 typographic
       defaults (smart quotes, guillemets, CJK brackets, ...) in 2.0
       (:ref:`brackets`)
   * - ``maiden_delimiters``
     - ``Policy.maiden_delimiters``
     - Same shape change as ``nickname_delimiters``. Precedence
       differs: in the 2.0 API a pair listed here wins over
       ``nickname_delimiters``; through the 1.x facade a pair in both
       buckets keeps parsing as ``nickname`` (v1 behavior;
       :ref:`brackets`)
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
     - 2.0 never capitalizes automatically during ``parse()``; call
       ``.capitalized()`` explicitly on the result instead

Every other ``regexes.*`` entry (``word``, ``spaces``, and the rest of
the compiled-pattern proxy) has no 2.0 replacement — parsing behavior
is configured entirely through named ``Policy`` fields now, not by
handing the parser a regex.

Comparison
----------

``HumanName.__eq__``/``__hash__`` were deprecated in 1.3.0 and are gone
in 2.0's core API; use ``matches()`` for "is this the same name?" and
``comparison_key()`` for dedup, dict keys, and sorting — both exist on
``HumanName`` and on :class:`~nameparser.ParsedName` with the same
behavior:

.. doctest::

    >>> from nameparser import HumanName, parse
    >>> hn = HumanName("de la Vega, Juan")
    >>> n = parse("de la Vega, Juan")
    >>> hn.matches("Juan de la Vega"), n.matches("Juan de la Vega")
    (True, True)
    >>> hn.comparison_key() == n.comparison_key()
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
differ between 1.4 and 2.x for specific input shapes. The full list,
with reasoning, is in each 2.x section of :doc:`release_log`.

Changed in 2.0
~~~~~~~~~~~~~~

These are the shapes worth grepping your own fixtures for, because a
recognized suffix or title now stays in its own field instead of
landing in ``first``/``last``:

.. doctest::

    >>> HumanName("Andrews, M.D.").last, HumanName("Andrews, M.D.").suffix
    ('Andrews', 'M.D.')
    >>> HumanName("Johnson PhD").first, HumanName("Johnson PhD").suffix
    ('Johnson', 'PhD')

Under 1.4 those read ``first="M.D."``/``last="Andrews"`` and
``first="Johnson"``/``last="PhD"`` respectively. Two more to check for:
a maiden marker now fills the ``maiden`` field rather than being folded
into ``middle``/``last`` (``"Jane Smith née Jones"``), and with a
custom suffix delimiter configured, a no-space delimiter group renders
whole (``"RN/CRNA"``) where 1.x split it (``"RN, CRNA"``) — the role
assignment is identical, only the rendered string differs.

East Asian names (2.1)
~~~~~~~~~~~~~~~~~~~~~~

2.1 adds three more, and unlike most of the 2.0 API these do reach
``HumanName``: a name written in East Asian script is read
family-first, an unspaced Korean name is split into surname and given
name, and the katakana middle dot separates tokens the way a space
does (:ref:`east-asian-names` explains the conventions).

.. doctest::

    >>> HumanName("毛 泽东").last
    '毛'
    >>> HumanName("김민준").last, HumanName("김민준").first
    ('김', '민준')

1.4 read the first as ``first="毛"``/``last="泽东"``, and left the
second whole in ``first``. The Korean one also changes what the name
*renders* as — ``str(HumanName("김민준"))`` was ``"김민준"`` and is now
``"민준 김"``, because the split inserts a token boundary that the
default format then writes given-name-first.

A third shape changes even though nothing splits it. 1.4 routed a lone
token to ``first`` whatever it was, so an unspaced Chinese or Japanese
name landed there entire; 2.1 reads it as native-script CJK and puts it
in ``last`` instead. Nothing is segmented — Han splitting is opt-in
through a locale pack and ``HumanName`` cannot apply one — but the
field the whole string arrives in is different:

.. doctest::

    >>> HumanName("毛泽东").last, HumanName("毛泽东").first
    ('毛泽东', '')
    >>> HumanName("山田太郎").last, HumanName("山田太郎").first
    ('山田太郎', '')

Both were ``first`` under 1.4. If you feed unspaced CJK through
``HumanName`` and read ``first``, that is the change most likely to
reach you, and it is silent — the string is intact, just in the other
field.

Japanese kana carries the same order rule, which widens both shapes
past the wholly-Han text described above. A name that mixes kanji with
hiragana or katakana is read family-first, and a lone kana-bearing
token moves from ``first`` to ``last`` exactly as ``毛泽东`` does:

.. doctest::

    >>> HumanName("高橋 みなみ").last, HumanName("高橋 みなみ").first
    ('高橋', 'みなみ')
    >>> HumanName("山田 エミ").last
    '山田'
    >>> HumanName("高橋みなみ").last, HumanName("高橋みなみ").first
    ('高橋みなみ', '')

1.4 read the spaced ones as ``first="高橋"``/``last="みなみ"`` and
``first="山田"``/``last="エミ"``, and put the unspaced one whole in
``first``. The spaced shapes change what the name renders as too:
``str(HumanName("高橋 みなみ"))`` was ``"高橋 みなみ"`` and is now
``"みなみ 高橋"``. A name written *wholly* in katakana is deliberately
left alone — it may be a transcribed foreign name already in
given-first order or a Japanese name's reading written family-first,
and the script cannot tell which (see :ref:`east-asian-names` to opt
in) — so ``HumanName("マイケル ジャクソン")`` reads
``first="マイケル"``/``last="ジャクソン"`` on both versions.

One more shape changes for a different reason: the katakana middle dot
``・``, which divides the parts of such a transcription, is now a token
separator rather than an ordinary character. 1.4 saw one token and put
it in ``first``; 2.1 sees two:

.. doctest::

    >>> HumanName("マイケル・ジャクソン").first
    'マイケル'
    >>> HumanName("マイケル・ジャクソン").last
    'ジャクソン'
    >>> HumanName("高橋・一郎").last, HumanName("高橋・一郎").first
    ('高橋', '一郎')

The two divide the same way and land in opposite fields, because the
katakana pair keeps its source order while the kanji pair takes the
family-first rule. Separating also changes the rendered string, the
same way the Korean split does: the dot comes back as a space, so
``str(HumanName("マイケル・ジャクソン"))`` was ``"マイケル・ジャクソン"``
and is now ``"マイケル ジャクソン"``. That reaches delimited content
too — the nickname in ``"山田 太郎 (マイケル・ジャクソン)"`` was
``"マイケル・ジャクソン"`` under 1.4 and is ``"マイケル ジャクソン"``
now.

Turning the East Asian readings off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Constants`` has no switch for any of this — the v1 configuration
surface is frozen for 2.x — so the way out is the 2.0 API
(:ref:`east-asian-defaults`):
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

Later releases moved more 1.4 readings, and these reach ``HumanName``
as well; 2.1 and 2.2 read every one of them as 1.4 did. The release
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
- ``capitalize()`` on ``"john smith md"``, ``"john smith phd"`` and
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
- ``capitalize()`` on ``"jacobus henricus van 't hoff"`` (2.5) — 1.4
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
- ``capitalize()`` on ``"j.r.r. tolkien"`` (2.6) — 1.4 wrote ``J.r.r.``;
  repair now capitalizes after a full stop or an ayn.
- ``"King Curtis"``, ``"Prince Fielder"``, ``"Sultan Khan"`` and
  ``"Sheikh Ahmed Khan"`` (2.7) — a title that is also a given name is a
  title only inside a title phrase or behind a style (``"His Majesty
  King Henry"``), so a bare one opening the name is the first name: 1.4
  read title ``King``, ``Prince``, ``Sultan`` and ``Sheikh``. The same
  holds for ``Princess``, ``Sultana``, ``Shaikh``, ``Sheik``, ``Shekh``,
  ``Shaik``, ``Cheikh``, ``Mahdi``, ``Bard``, ``Buddha``, ``Siddha``,
  ``Gyani`` and ``Wing``, and for a lone qualifier such as ``Grand``.
  ``Constants().titles`` still lists these words, so adding one there
  changes nothing; the 2.0 API's ``Lexicon.default().add(titles={"king"})``
  makes one a title everywhere.
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

.. doctest::

    >>> HumanName("Jack MA").suffix
    'MA'
    >>> HumanName("Her Majesty Queen Elizabeth").first
    'Elizabeth'
    >>> HumanName("His Royal Highness Prince Harry").first
    'Harry'
    >>> king = HumanName("Dr King Jr")
    >>> king.title, king.last, king.suffix
    ('Dr', 'King', 'Jr')
    >>> HumanName("John Smith Prof.").title
    'Prof.'
    >>> HumanName("jose e maria santos").middle
    'e maria'
    >>> HumanName("van der Berg, PhD").last
    'van der Berg'
    >>> HumanName("Josep Carod i Rovira").last
    'Carod i Rovira'
    >>> HumanName("Jane Smith N.C.C.").suffix
    'N.C.C.'
    >>> HumanName("Jane Smith, LEED AP").suffix
    'LEED AP'
    >>> holder = HumanName("Eric H. Holder Jr. Attorney General")
    >>> holder.title, holder.last, holder.suffix
    ('Attorney General', 'Holder', 'Jr.')
    >>> HumanName("Eric H. Holder, Jr., Attorney General").title
    'Attorney General'
    >>> HumanName("Steven Hardman, RN - CRNA").suffix
    'RN, CRNA'
    >>> HumanName("John van der Berg Prof.").last
    'van der Berg'
    >>> HumanName("Liam Ó Murchú").last
    'Ó Murchú'
    >>> HumanName("Herra Väinö Johansson").title
    'Herra'
    >>> HumanName("山田 ﾀﾛｳ").last
    '山田'
    >>> md = HumanName("john smith md")
    >>> md.capitalize(force=True)
    >>> str(md)
    'John Smith MD'
    >>> phd = HumanName("john smith phd")
    >>> phd.capitalize()
    >>> str(phd)
    'John Smith PhD'
    >>> mba = HumanName("JANE DOE MBA")
    >>> mba.capitalize()
    >>> str(mba)
    'Jane Doe MBA'
    >>> HumanName("john e smith").initials()
    'j. e. s.'
    >>> dr = HumanName("Dr. Smith, John")
    >>> dr.title, dr.first, dr.last
    ('Dr.', 'John', 'Smith')
    >>> HumanName("Gov Smith").title
    'Gov'
    >>> HumanName("Antonio Pavlović mlađi").suffix
    'mlađi'
    >>> HumanName("John Smith II, AD").suffix
    'II, AD'
    >>> HumanName("John III, Sir").first
    'John'
    >>> HumanName("Smith, Sir").first
    'Smith'
    >>> HumanName("Ivoi, Paul d'").last
    "d' Ivoi"
    >>> HumanName("jose j y lopez").middle
    'j y'
    >>> HumanName("Bapak Dwi Putro").title
    'Bapak'
    >>> vant = HumanName("jacobus henricus van 't hoff")
    >>> vant.capitalize(force=True)
    >>> str(vant)
    "Jacobus Henricus van 't Hoff"
    >>> HumanName("Maria de Sa").last
    'de Sa'
    >>> HumanName("John Smith SA").last
    'SA'
    >>> HumanName("Cllr John Smith").title
    'Cllr'
    >>> HumanName("Dott.ssa Anna Bianchi").title
    'Dott.ssa'
    >>> HumanName("José Silva Júnior").suffix
    'Júnior'
    >>> HumanName("John Smith, MD; PhD").suffix
    'MD; PhD'
    >>> md_karim = HumanName("Mr Md Karim Uddin")
    >>> md_karim.title, md_karim.first
    ('Mr', 'Md')
    >>> HumanName("Wm Smith").first
    'Wm'
    >>> HumanName("Doe, Jane Mrs").title
    'Mrs'
    >>> HumanName("\u200bDr. John Smith").title
    'Dr.'
    >>> tolkien = HumanName("j.r.r. tolkien")
    >>> tolkien.capitalize()
    >>> str(tolkien)
    'J.R.R. Tolkien'
    >>> [HumanName(n).first for n in ("King Curtis", "Prince Fielder",
    ...     "Princess Diana", "Sultan Khan", "Sultana Begum",
    ...     "Sheikh Ahmed Khan", "Shaikh Ahmed Khan", "Sheik Ahmed",
    ...     "Shekh Ahmed", "Shaik Ahmed", "Cheikh Anta Diop",
    ...     "Mahdi Karimi", "Bard Larsen", "Buddha Bahadur Tamang",
    ...     "Siddha Raj Joshi", "Gyani Maya Gurung", "Wing Lau")]
    ... # doctest: +NORMALIZE_WHITESPACE
    ['King', 'Prince', 'Princess', 'Sultan', 'Sultana', 'Sheikh', 'Shaikh',
     'Sheik', 'Shekh', 'Shaik', 'Cheikh', 'Mahdi', 'Bard', 'Buddha',
     'Siddha', 'Gyani', 'Wing']
    >>> HumanName("His Majesty King Henry").title
    'His Majesty King'
    >>> HumanName("Chief Justice John Roberts").title
    'Chief Justice'
    >>> HumanName("Major General John Smith").title
    'Major General'
    >>> HumanName("Chas. Smith").first, HumanName("Ma. Cristina Reyes").first
    ('Chas.', 'Ma.')
    >>> HumanName("John Smith VI MD").suffix, HumanName("Smith, John VI").suffix
    ('VI MD', 'VI')
    >>> HumanName("John Smith, MD/PhD").suffix
    'MD/PhD'
    >>> HumanName("John Smith, Pharm D").suffix
    'Pharm D'
    >>> HumanName("John Smith Ph. D. Jones").suffix
    'Ph. D. Jones'
    >>> HumanName("Smith, John MA Jones").suffix
    'MA Jones'
    >>> HumanName("Pedro Alves Filho").suffix
    'Filho'
    >>> HumanName("Alexandre Dumas fils").last
    'Dumas'
    >>> HumanName("Andrew Perkins (JD)").suffix
    'JD'
    >>> HumanName("Jane Smith, Dr. / MD").first
    'Jane'
    >>> HumanName("Marie Bon Durand").last
    'Durand'
    >>> HumanName("Herren Hans").first
    'Herren'
    >>> HumanName("Marquis Johnson").first, HumanName("Johnson, Marquise").first
    ('Marquis', 'Marquise')
    >>> HumanName("Marquis of Queensberry").title
    'Marquis of Queensberry'
    >>> [HumanName(n).first for n in ("Deacon Jones", "Burgess Meredith",
    ...     "Ranger Smith")]
    ['Deacon', 'Burgess', 'Ranger']
    >>> HumanName("Deacon of the Church Jane Smith").title
    'Deacon of the Church'
    >>> HumanName("Queen Latifah").first, HumanName("Elizabeth II, Queen").first
    ('Queen', 'Queen')
