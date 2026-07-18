Migrating from HumanName
=========================

Nothing breaks. 2.0 keeps ``HumanName`` and ``CONSTANTS`` working
exactly as before — same imports, same attributes, same mutation API
(``name.C.titles.add(...)``, ``name.first = "..."``, and so on).
Upgrading to 2.0 and migrating your code to the new
:class:`~nameparser.Parser`/:class:`~nameparser.Lexicon`/
:class:`~nameparser.Policy` API are two separate decisions — you can do
the former today and the latter whenever it's convenient, or never. The
compatibility layer (``HumanName`` and ``nameparser.config``) is
removed in 3.0; that release is not scheduled.

The full 1.x documentation remains the canonical reference for
``HumanName`` and stays online at the readthedocs ``stable`` build,
currently the 1.4.0 release: https://nameparser.readthedocs.io/en/stable/

This page exists for the other direction: translating a v1
customization or a v1-shaped comparison into the 2.0 API, one row per
old name.

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
       once
   * - ``capitalize()``, ``force_mixed_case_capitalization``
     - ``capitalized(lexicon, force=...)``
     - :meth:`~nameparser.ParsedName.capitalized` returns a new value
       rather than mutating in place

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

And behavior/render scalars map onto :class:`~nameparser.Policy` (or a
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
     - Was a three-sentinel dict; now a plain ``frozenset`` of
       ``(open, close)`` pairs
   * - ``maiden_delimiters``
     - ``Policy.maiden_delimiters``
     - Same shape change as ``nickname_delimiters``
   * - ``regexes.bidi``
     - ``Policy.strip_bidi``
     - ``regexes.bidi = False`` becomes ``Policy(strip_bidi=False)``
   * - ``regexes.emoji``
     - ``Policy.strip_emoji``
     - ``regexes.emoji = False`` becomes ``Policy(strip_emoji=False)``
   * - ``force_mixed_case_capitalization``
     - ``capitalized(force=True)``
     - Moves from stored config to a per-call argument
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
case-pairs compare equal than did under 1.4 (see the 2.0.0 section of
:doc:`release_log` for the exact rule and examples).

Behavior changes
-----------------

Beyond the API surface mapped above, a handful of parse *outputs*
differ between 1.4 and 2.0 for specific input shapes — comma-suffix
routing, maiden-marker detection, an ambiguous-acronym data change, and
one rendering difference under a custom suffix delimiter. These are
listed with their reasoning and test coverage in the 2.0.0 section of
:doc:`release_log`; they aren't repeated here.
