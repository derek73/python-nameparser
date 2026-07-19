Locale packs
============

A locale pack is an opt-in bundle of policy — and, when a naming
tradition needs it, vocabulary — for one specific pattern: East Slavic
patronymics, Turkic patronymic markers, and so on. Packs apply only
when you ask for one by name, and every pack makes the same promise:
a pack never changes a name it doesn't declare.

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
    ('ru', 'tr_az')
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

Both shipped packs are policy-only — they carry no vocabulary of their
own; see :doc:`concepts` for why that split (language vocabulary vs.
behavior) is drawn where it is.

Creating your own Locale
-------------------------

You don't need to touch nameparser's registry to use your own pack —
:class:`~nameparser.Locale` is a plain, constructible value:
``Locale(code=..., lexicon=..., policy=PolicyPatch(...))``. A
:class:`~nameparser.PolicyPatch` is a :class:`~nameparser.Policy`-shaped
patch: every field defaults to :data:`~nameparser.UNSET` (leave it
alone) instead of to a concrete value, so a pack only ever states what
it changes.

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
#. Add a rotator list to ``tests/v2/test_locales.py`` with at least one
   name exercising every alternation branch of every marker regex the
   pack defines — ``test_rotators_cover_every_marker_branch`` fails
   until each branch is hit.
#. Keep the non-interference gate green over the shared corpus plus
   your rotators: every name the packed parser parses differently from
   the default must be one your ``DEVIATES`` predicate flags — no
   silent, undeclared side effects on names outside the pack's stated
   scope.
#. Keep the pack policy-only in 2.0 — ``ru`` and ``tr_az`` both ship
   an empty :class:`~nameparser.Lexicon`; a pack that wants to carry
   its own vocabulary is a later conversation.
#. Curate vocabulary conservatively, the same rule as
   :doc:`customize`: when you're unsure whether a word or a marker
   belongs, leave it out.

``nameparser/locales/ru.py`` is the reference implementation to copy
from. Staged packs in progress are tracked in issues `#271
<https://github.com/derek73/python-nameparser/issues/271>`_, `#272
<https://github.com/derek73/python-nameparser/issues/272>`_, and `#146
<https://github.com/derek73/python-nameparser/issues/146>`_.
