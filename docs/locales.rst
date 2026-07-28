Locale packs
============

A locale pack is an opt-in bundle of policy — and, when a naming
tradition needs it, vocabulary — for one specific pattern: East Slavic
patronymics, Turkic patronymic markers, and so on. Packs apply only
when you ask for one by name, and every pack makes the same promise:
it never changes a name outside the shapes it declares. Read that
precisely — a shape is a pattern, not a language, so a pack can act on
a name from a tradition it was not written for. The warning under
`Using a pack`_ shows what that costs.

What works without a pack
--------------------------

Most international names need no pack at all. The default vocabulary
covers five scripts — Latin, Cyrillic, Greek, Arabic and Hebrew, plus
Devanagari titles — so honorifics, conjunctions and name particles in
those scripts are recognized out of the box:

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("الشيخ محمد بن سلمان")
    >>> name.title, name.given, name.family
    ('الشيخ', 'محمد', 'بن سلمان')
    >>> parse("عبد الرحمن محمد").given
    'عبد الرحمن'

Native-script entries are safe to enable by default precisely because
they cannot collide with Latin-script names. That rules out the
reverse: transliterations like ``sri``/``shri`` are *not* in the
default vocabulary, because they are also ordinary given names in
Latin script. The same conservatism holds back a handful of native
entries that collide within their own script — bare ``سيد`` and
``شيخ`` (common given names), Hebrew ``רב`` (an ordinary word), the
Arabic ``د.`` abbreviation (it would swallow initials).

If your data is homogeneous enough that a collision can't occur, the
reasoning behind the default doesn't apply to you — add the entry:

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> lex = Lexicon.default().add(
    ...     titles={"سيد"}, given_name_titles={"سيد"})
    >>> name = Parser(lexicon=lex).parse("سيد محمد")
    >>> name.title, name.given
    ('سيد', 'محمد')

Both fields, because ``given_name_titles`` is a marker over ``titles``
rather than a separate vocabulary: ``titles`` makes the word a title at
all, and listing it in ``given_name_titles`` says the honorific
precedes the *given* name — as Arabic ones do — so the word after it
isn't read as a family name. Listing it in ``given_name_titles`` alone
raises ``ValueError`` rather than quietly doing nothing.

Two East Asian behaviors are on by default for the same reason, except
that what selects them is the *script* rather than the word: a name
written wholly in Han or Hangul reads family-first, and an unspaced
Korean name is split into surname and given name. Chinese and Japanese
both write family-first natively, so reading the order takes no guess
about which language it is; hangul is written by nothing but Korean,
whose surnames are a closed census set, so splitting is safe too. See
:ref:`east-asian-names` in :doc:`usage` for what that looks like and
how to turn either half off. Splitting an unspaced *Han* name is the
one piece that does need to know the language — a Chinese surname list
mangles Japanese kanji names — so that half waits for the ``zh`` pack.

A pack is for something different: a *structural* rule, like reordering
a patronymic, that vocabulary alone can't express.

Using a pack
------------

:func:`~nameparser.parser_for` folds one or more packs onto a base
:class:`~nameparser.Parser` (the module default, unless you pass
``base=``). Here the Russian pack reads "Сидоров Иван Петрович"
(Sidorov Ivan Petrovich — surname/given/patronymic order) the way a
formal Russian document intends:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> ru = parser_for(locales.RU)
    >>> ru.parse("Сидоров Иван Петрович").given
    'Иван'

Packs stack: pass more than one pack and their policies fold together
in order.

.. doctest::

    >>> both = parser_for(locales.RU, locales.TR_AZ)
    >>> sorted(rule.name for rule in both.policy.patronymic_rules)
    ['EAST_SLAVIC', 'TURKIC']

Find what's shipped with :func:`~nameparser.locales.available`, and
look one up dynamically by its lowercase code with
:func:`~nameparser.locales.get` — the same code the ``--locale`` flag
takes:

.. doctest::

    >>> locales.available()
    ('ru', 'tr_az', 'zh')
    >>> locales.get("ru") is locales.RU
    True

The command line accepts the same codes: ``python -m nameparser
--locale ru --json "Сидоров Иван Петрович"`` applies the pack before
parsing, equivalent to ``parser_for(locales.get("ru"))``.

.. list-table:: Shipped packs
   :header-rows: 1
   :widths: 15 85

   * - Code
     - Turns on
   * - ``ru``
     - East Slavic patronymic order — detects a formal
       given/patronymic/family shape (Cyrillic and transliterated
       ``-ovich``/``-ovna``-style endings) and assigns it accordingly.
   * - ``tr_az``
     - Turkic patronymic markers — detects a standalone marker token
       (``oglu``, ``qizi``, ``uulu``, and their Latin- and
       Cyrillic-script variants) and reads the name around it as
       given/middle/family.
   * - ``zh``
     - Chinese surname segmentation — splits an unspaced Han name into
       surname and given name (``毛泽东`` → family ``毛``, given
       ``泽东``) against the surname list the pack ships. It sets no
       name order: native-script Han already reads family-first
       without a pack.

``ru`` and ``tr_az`` are policy-only — they carry no vocabulary of
their own. ``zh`` is both halves at once: a surname list, plus the one
policy field that turns segmentation on for the script it covers. See
:doc:`concepts` for how that split (language vocabulary vs. behavior)
is drawn, and `Contributing a pack to nameparser`_ for which half a
new naming rule belongs in.

.. warning::

   A pack declares a name *shape*, not a language, and it cannot tell
   whose name it is looking at. Any surname that happens to end in a
   patronymic suffix matches the East Slavic rule, including names
   that are not East Slavic at all:

   .. doctest::

       >>> ru = parser_for(locales.RU)
       >>> name = ru.parse("David Michael Abramovich")
       >>> name.given, name.family
       ('Michael', 'David')

   The default parser reads that as given ``David``, family
   ``Abramovich``. This is the trade the pack asks you to make, and it
   is why packs are opt-in rather than automatic: enable one only for
   data that is predominantly in the order it detects. If your input
   mixes traditions, parse the subsets separately with different
   parsers rather than enabling a pack over all of it.

Creating your own Locale
-------------------------

You don't need to touch nameparser's registry to use your own pack —
:class:`~nameparser.Locale` is a plain, constructible value:
``Locale(code=..., lexicon=..., policy=PolicyPatch(...))``. A
:class:`~nameparser.PolicyPatch` is a :class:`~nameparser.Policy`-shaped
patch: every field defaults to :data:`~nameparser.UNSET` (leave it
alone) instead of to a concrete value, so a pack only ever states what
it changes. A patch can also be applied directly, without a pack —
see :meth:`Policy.patched() <nameparser.Policy.patched>`.

The ``policy`` half works that way, but the ``lexicon`` half does not.
A pack's :class:`~nameparser.Lexicon` is a complete value in its own
right and is validated on its own, before it is unioned onto the base
— so a fragment that marks a word must also carry the word it marks.
To make an existing base title precede the given name, restate the
title in the fragment rather than listing it in ``given_name_titles``
alone. ``zh`` is the shipped worked example: its
``Lexicon(surnames=...)`` has to satisfy every ``Lexicon`` rule
standing alone, before anything unions it onto the base.

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, parser_for
    >>> lex = Lexicon.empty().add(titles={"kapitan"})
    >>> mine = Locale(code="mycorp", lexicon=lex,
    ...                policy=PolicyPatch(middle_as_family=True))
    >>> name = parser_for(mine).parse("Kapitan Anna Maria Schmidt")
    >>> name.title, name.given, name.family
    ('Kapitan', 'Anna', 'Maria Schmidt')

That pack does two things at once: the :class:`~nameparser.Lexicon`
fragment teaches the parser that ``kapitan`` is a title, and the
:class:`~nameparser.PolicyPatch` turns on ``middle_as_family`` so any
remaining given-position words after the first fold into ``family``
instead of ``middle`` — compare this to the default parser's reading
of the same string, which has no title and splits ``given='Kapitan'``,
``middle='Anna Maria'``, ``family='Schmidt'``.

When ``parser_for`` folds one or more packs onto a base, lexicons
union (a pack's words are added to the base's, never removed); policy
fields declared as set-valued in :class:`~nameparser.PolicyPatch`
(``patronymic_rules`` and the delimiter fields) union the same way;
and every other, scalar field is later-wins — if two packs (or a pack
and an explicit conflicting value) set the same scalar field, the last
one applied wins and a ``UserWarning`` is raised so the conflict
isn't silent.

Contributing a pack to nameparser
----------------------------------

Shipping a pack in nameparser itself (rather than keeping it local to
your own code) means meeting the in-repo contract, checked mechanically
by ``tests/v2/test_locales.py``:

#. Add a registry entry in ``nameparser/locales/__init__.py`` — a
   ``"CODE": ("module.path", "ATTR")`` row in ``_REGISTRY``, so the
   pack loads lazily on first access (importing ``nameparser.locales``
   never imports pack modules).
#. Declare a module-level ``DEVIATES(name)`` predicate: given a name
   string, return whether *this pack alone* might parse it differently
   from the default parser. Over-declaring is safe; under-declaring is
   not — when in doubt, ``DEVIATES`` should say yes.
#. Add a rotator list to ``tests/v2/test_locales.py``. Every pack needs
   one, but what it has to contain follows from how the pack declares
   its scope. A pack declaring by *marker regex* (``ru``, ``tr_az``)
   needs at least one name exercising every alternation branch of every
   regex it defines — ``test_rotators_cover_every_marker_branch`` fails
   until each branch is hit. A pack declaring by *codepoint range*
   (``zh``) has no branches to sweep and drops out of that test, so its
   rotators have to carry the same weight by hand: the unspaced names
   the pack must split, one per shape of the vocabulary it ships —
   single surname, compound surname, and any spelling variant it means
   to cover.
#. Keep the non-interference gate green over the shared corpus plus
   your rotators: every name the packed parser parses differently from
   the default must be one your ``DEVIATES`` predicate flags — no
   silent, undeclared side effects on names outside the pack's stated
   scope.
#. Decide which layer the vocabulary belongs in, if the pack carries
   any. Vocabulary that is *self-selecting* — able to match only text of
   the tradition it came from, the way a hangul surname can only ever
   match hangul — is default-safe, and belongs in the default lexicon
   (``nameparser/config/``) rather than in a pack: a pack nobody knows
   to ask for is vocabulary nobody gets. Vocabulary that *declares a
   language its script does not* — a Chinese surname list, which
   silently mangles the Japanese names written in the same characters
   — belongs in the pack, where asking for it is the declaration.
   ``ru`` and ``tr_az`` need no vocabulary at all and ship an empty
   :class:`~nameparser.Lexicon`; ``nameparser/locales/zh.py`` is the
   template for one that does.
#. Curate vocabulary conservatively, the same rule as
   :doc:`customize`: when you're unsure whether a word or a marker
   belongs, leave it out.

``nameparser/locales/ru.py`` is the reference implementation for a
policy-only pack, ``nameparser/locales/zh.py`` for one that carries
vocabulary. Packs still in progress are tracked in issues `#272
<https://github.com/derek73/python-nameparser/issues/272>`_ (Japanese)
and `#146 <https://github.com/derek73/python-nameparser/issues/146>`_
(Vietnamese).
