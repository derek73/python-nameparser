Migrating from HumanName
=========================

``HumanName`` and ``CONSTANTS`` keep working in 2.0 — same imports,
same attributes, same mutation API (``name.C.titles.add(...)``,
``name.first = "..."``, and so on). Upgrading to 2.0 and migrating your
code to the new :class:`~nameparser.Parser`/:class:`~nameparser.Lexicon`/
:class:`~nameparser.Policy` API are two separate decisions — you can do
the former today and the latter whenever it's convenient. The
compatibility layer (``HumanName`` and ``nameparser.config``) is
removed in 3.0; that release is not scheduled.

The full 1.x documentation remains the canonical reference for
``HumanName`` and stays online at the readthedocs ``stable`` build,
currently the 1.4.0 release: https://nameparser.readthedocs.io/en/stable/

This page exists for the other direction: translating a v1
customization or a v1-shaped comparison into the 2.0 API, one row per
old name.

Before you upgrade
------------------

What 2.0 removes is the batch of deprecations 1.3 and 1.4 announced. If
your test suite runs clean on 1.4 under ``python -W
error::DeprecationWarning``, it will run on 2.0 — with four exceptions
that 1.4 never warned about. The first three raise the first time you
hit them; the fourth only warns, so read it carefully:

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

One removal changes results without saying anything. ``HumanName`` no
longer defines ``__eq__``, so ``name == "John Smith"`` is now ``False``
where 1.x returned ``True``. That one *did* warn on 1.4, but nothing
will tell you on 2.0. If you compare names anywhere, grep for ``==``
before upgrading and move to ``matches()`` — see `Comparison`_.

One step has to happen *before* you upgrade, because the fix is only
available on the version you're leaving: a ``Constants`` pickle written
by nameparser 1.2.x or earlier must be re-pickled under 1.3 or 1.4.
2.0 refuses to load one, and by then the code that could rewrite it is
gone.

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
       for a private snapshot of the current shared config
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
ours, ``tools/differential/`` in the source repository diffs 1.4 and
2.0 parses over a corpus of names you supply. It is development
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
     - A per-call argument now, not stored config — see :doc:`customize`
   * - ``initials_format``, ``initials_delimiter``, ``initials_separator``
     - ``initials(spec, delimiter, separator)``
     - Same three knobs, now call-site arguments to
       :meth:`~nameparser.ParsedName.initials`
   * - ``suffix_delimiter``
     - ``Policy(extra_suffix_delimiters={...})``
     - Moves from a ``HumanName``/``Constants`` scalar to a ``Policy``
       set field, so more than one custom delimiter can be active at
       once. It is the *set* that moved, not just the name: passing the
       old scalar through (``extra_suffix_delimiters=" - "``) raises,
       rather than silently registering three one-character delimiters
   * - ``capitalize(force=...)``
     - ``capitalized(force=...)``
     - :meth:`~nameparser.ParsedName.capitalized` returns a new value
       rather than mutating in place. Its optional first argument takes
       a :class:`~nameparser.Lexicon`, if you need custom
       capitalization exceptions

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

Config map
----------

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
     - Pair-valued; set it via ``dataclasses.replace(lexicon,
       capitalization_exceptions={...})``, not ``add()``/``remove()``

The vocabulary that feeds both columns lives in ``nameparser.config``,
and in 2.2 its module and constant names moved to the same terminology
the ``Lexicon`` column uses. If you import the default word lists
directly — to read one, extend one, or copy one into your own
configuration — four vocabularies moved:

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

Every 1.x name still resolves — by attribute access, by ``from ...
import``, and by ``from ... import *``. Reading one emits a
``DeprecationWarning`` naming the module and constant to move to, then
returns the constant from its new home; the warning fires once per name
per process, and the old names are removed in 3.0. Only the data layer
moved: the ``CONSTANTS`` attribute names in the field-mapping table
above are v1 facade surface and are unaffected, so ``constants.prefixes``,
``constants.non_first_name_prefixes``, ``constants.bound_first_names``,
``constants.first_name_titles`` and ``constants.suffix_not_acronyms``
keep their 1.x spelling for as long as the facade exists.

Every vocabulary set in ``nameparser.config`` is also a ``frozenset``
as of 2.2 — the renamed ones and the rest, ``CAPITALIZATION_EXCEPTIONS``
being a mapping and unchanged. That retires one 1.x idiom outright:
``TITLES.add("dean")`` — editing a default word list in place — now
raises ``AttributeError`` at the line that writes it, rather than
changing some parses and not others some distance away.

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

Configure the objects instead, which both APIs have always supported
and neither the freeze nor the rename affects. For ``HumanName``, build
a private ``Constants`` and pass it::

    from nameparser import HumanName
    from nameparser.config import Constants

    constants = Constants()
    constants.titles.add("dean")
    name = HumanName("Dean Smith", constants=constants)

For the 2.0 API, extend the default lexicon and hand it to a parser::

    from nameparser import Lexicon, Parser

    parser = Parser(lexicon=Lexicon.default().add(titles={"dean"}))
    name = parser.parse("Dean Smith")

Mutating the shared ``CONSTANTS`` singleton still works and still
reaches every ``HumanName`` that reads it, but it warns: it is
deprecated along with the rest of the v1 facade and goes away in 3.0.
Prefer a private ``Constants`` in new code. See :doc:`customize` for
the full set of knobs on each.

Behavior and render scalars map onto :class:`~nameparser.Policy` (or a
rendering argument, where the 2.0 equivalent isn't config at all):

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - ``CONSTANTS``
     - 2.0 equivalent
     - Note
   * - ``patronymic_name_order``
     - ``Policy(patronymic_rules={PatronymicRule.EAST_SLAVIC,
       PatronymicRule.TURKIC})``
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
   * - ``maiden_delimiters``
     - ``Policy.maiden_delimiters``
     - Same shape change as ``nickname_delimiters``. Precedence
       differs: in the 2.0 API a pair listed here wins over
       ``nickname_delimiters``; through the 1.x facade a pair in both
       buckets keeps parsing as ``nickname`` (v1 behavior)
   * - ``regexes.bidi``
     - ``Policy.strip_bidi``
     - ``regexes.bidi = False`` becomes ``Policy(strip_bidi=False)``
   * - ``regexes.emoji``
     - ``Policy.strip_emoji``
     - ``regexes.emoji = False`` becomes ``Policy(strip_emoji=False)``
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

.. warning::

   ``non_first_name_prefixes`` and ``particles_ambiguous`` mark
   **complementary** sets, not the same set under a new name.
   ``non_first_name_prefixes`` lists particles that are *never* read as
   a given name; ``particles_ambiguous`` lists the particles that
   *may* be read as one. Translating a customization means flipping
   the set: ``particles_ambiguous = lexicon.particles -
   constants.non_first_name_prefixes``. Copying
   ``non_first_name_prefixes`` straight into ``particles_ambiguous``
   silently inverts which particles are allowed to double as a given
   name.

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
differ between 1.4 and 2.0 for specific input shapes. The full list,
with reasoning, is in the 2.0.0 section of :doc:`release_log`. These
are the shapes worth grepping your own fixtures for, because a
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

2.1 adds three more, and unlike most of the 2.0 API these do reach
``HumanName``: a name written in East Asian script is read
family-first, an unspaced Korean name is split into surname and given
name, and the katakana middle dot separates tokens the way a space
does.

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
left alone — it is usually a transcribed foreign name already in
given-first order — so ``HumanName("マイケル ジャクソン")`` reads
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

``Constants`` has no switch for any of this — the v1 configuration
surface is frozen for 2.x — so the way out is the 2.0 API:
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
