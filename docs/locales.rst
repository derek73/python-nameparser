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

Most international names need no pack at all. Besides Latin, the
default vocabulary covers Cyrillic, Greek, Arabic, Hebrew, Devanagari
and Bengali, and the East Asian scripts described below. Honorifics,
conjunctions and name particles written in them are recognized out of
the box, as far as each script's vocabulary reaches: each of those
scripts but katakana ships honorifics, while conjunctions and particles
reach fewer — Cyrillic and Greek ship conjunctions and no particle,
Hebrew particles and no conjunction, and Devanagari, Bengali, Han,
Hangul and hiragana honorifics only.

.. doctest::

    >>> from nameparser import parse
    >>> shaikh = parse("الشيخ محمد بن سلمان")
    >>> shaikh.title, shaikh.given, shaikh.family
    ('الشيخ', 'محمد', 'بن سلمان')
    >>> parse("عبد الرحمن محمد").given
    'عبد الرحمن'

Adding a word the defaults hold back
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
    >>> sayyid_lex = Lexicon.default().add(
    ...     titles={"سيد"}, given_name_titles={"سيد"})
    >>> sayyid = Parser(lexicon=sayyid_lex).parse("سيد محمد")
    >>> sayyid.title, sayyid.given
    ('سيد', 'محمد')

Both fields, because ``given_name_titles`` is a marker over ``titles``
rather than a separate vocabulary: ``titles`` makes the word a title at
all, and listing it in ``given_name_titles`` says the honorific
precedes the *given* name — as Arabic ones do — so the word after it
isn't read as a family name. Listing it in ``given_name_titles`` alone
does nothing, and says nothing: the word is never read as a title, so
the entry is never consulted.

East Asian names need no pack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two East Asian behaviors are on by default for the same reason, except
that what selects them is the *script* rather than the word
(:ref:`east-asian-defaults` covers turning them off). The background
(covered fully under :ref:`east-asian-names`): Chinese, Japanese, and Korean names put the family name
first in native script and are usually written with no space between
the parts. Both defaults follow from facts the script alone
establishes. A name written wholly in Han or Hangul — or in kanji and
kana other than katakana alone, which only Japanese produces — is assigned
family-first, because every language written in those scripts orders
names that way; no language guess is involved. An unspaced hangul
name is additionally split into surname and given name, because hangul
is written by nothing but Korean and Korean surnames are a closed
census set that ships as default vocabulary. Splitting an unspaced
*Han* name is the one behavior the script cannot license — the same
characters could be a Chinese or a Japanese name, and a Chinese
surname list splits Japanese names in the wrong place — so it is not a
default: the ``zh`` and ``ja`` packs below turn it on for data whose
language you can declare.

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

Stacking packs
~~~~~~~~~~~~~~

Pass more than one pack and they fold together in order:

.. doctest::

    >>> both = parser_for(locales.RU, locales.TR_AZ)
    >>> sorted(rule.name for rule in both.policy.patronymic_rules)
    ['EAST_SLAVIC', 'TURKIC']

How each part combines:

- **Languages union** into one choice, applied first (see
  `Choosing languages`_), so the order the packs are given in does not
  change it.
- **Lexicons union**: a pack's own words are added to the base's,
  after the choice, never removed.
- **Set-valued policy fields union** the same way — the fields
  declared set-valued in :class:`~nameparser.PolicyPatch`:
  ``patronymic_rules``, ``segment_scripts`` and the delimiter fields.
- **Every other, scalar field is later-wins.** If two packs with
  different codes set the same scalar field — even to the same value —
  the later one wins and a ``UserWarning`` is raised; a pack overrides
  the base parser's value silently.

Choosing languages
~~~~~~~~~~~~~~~~~~

The default vocabulary is written one word at a time, each in the file
of the language whose names it occurs in, and the default reads every
language's words at once. Where two languages read one word
differently, the default keeps both readings and lets the name around
the word decide: Portuguese ``e`` ("and") is also an initial, so in a
name written wholly in capitals it reads as the initial and reports the
doubt.

A :class:`~nameparser.Locale` with ``languages`` chooses languages,
written as BCP 47 tags. A chosen language's readings win on a word it
has a vocabulary reading of, and a reading its file holds off by
default is turned on. Under Portuguese, ``E`` is the connective:

.. doctest::

    >>> from nameparser import Lexicon, Locale, parse, parser_for
    >>> parse("ANA SILVA E SOUZA").family
    'SOUZA'
    >>> pt = Locale(code="pt", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"pt"}))
    >>> parser_for(pt).parse("ANA SILVA E SOUZA").family
    'SILVA E SOUZA'

A choice costs the other languages' readings of the words it settles.
English holds ``DO`` as a credential (Doctor of Osteopathy) and
Portuguese ``do`` as a particle ("of the"), so each language, chosen
alone, reads the other's names by its own word:

.. doctest::

    >>> en = Locale(code="en", lexicon=Lexicon.empty(),
    ...             languages=frozenset({"en"}))
    >>> parse("Maria do Carmo").family
    'do Carmo'
    >>> parser_for(en).parse("Maria do Carmo").family
    'Carmo'
    >>> parser_for(pt).parse("John Smith DO").family
    'DO'
    >>> parser_for(pt, en).parse("Maria do Carmo").family
    'do Carmo'

Choosing both keeps both readings, as the default does. A reading
that a word is borne as a name never settles anything: it keeps the
name around the word in charge, under any choice.

A tag selects its own file and those of the languages it belongs to,
never the other way: ``pt-BR`` reads ``pt.toml`` too, and ``pt``
leaves the Brazilian words alone. No other table of related languages
is read, so a caller with Malay and Indonesian names chooses ``ms``
and ``id``. Tags are compared without regard to case, and a tag is
checked in one of three ways:

- **A malformed tag** (``pt_BR``, ``p``) raises ``ValueError`` when the
  :class:`~nameparser.Locale` is built.
- **A tag no vocabulary file holds**, itself or any language it belongs
  to (``xx``), raises ``ValueError`` at
  :func:`~nameparser.parser_for`, naming the tags that have a file.
- **A region or other subtag of a language that has a file** (``pt-PT``)
  is accepted and reads that language's file, there being none of its
  own.

A pack that chooses no language leaves the base parser's vocabulary
exactly as it was.

Choosing in one call
^^^^^^^^^^^^^^^^^^^^

A choice belongs to one :func:`~nameparser.parser_for` call: the
languages of the packs passed together are one choice. A base parser
records no choice of its own, so a choice made on top of a base built
by an earlier call applies after the base's, and settles the base's
words its own way. To choose two languages, pass both packs in one
call:

.. doctest::

    >>> chained = parser_for(en, base=parser_for(pt))
    >>> chained.parse("Maria do Carmo").family
    'Carmo'
    >>> chained.parse("John Smith DO").family
    'DO'
    >>> together = parser_for(pt, en)
    >>> together.parse("Maria do Carmo").family, together.parse("John Smith DO").suffix
    ('do Carmo', 'DO')

A choice applied to a base also removes what it drops from the base's
vocabulary, even where you added the word yourself, and keeps every
word it does not touch. Under ``en``, a base listing ``do`` and ``van``
as particles keeps only ``van``, English holding ``do`` as a
credential:

.. doctest::

    >>> from nameparser import Parser
    >>> mine = Lexicon(particles=frozenset({"do", "van"}),
    ...                surnames=Lexicon.default().surnames)
    >>> sorted(parser_for(en, base=Parser(lexicon=mine)).lexicon.particles)
    ['van']

Finding packs by code
~~~~~~~~~~~~~~~~~~~~~

Find what's shipped with :func:`~nameparser.locales.available`, and
look one up dynamically by its lowercase code with
:func:`~nameparser.locales.get`:

.. doctest::

    >>> locales.available()
    ('ja', 'ru', 'tr_az', 'zh')
    >>> locales.get("ru") is locales.RU
    True

The command line accepts the same codes: ``python -m nameparser
--locale ru --json "Сидоров Иван Петрович"`` applies the pack before
parsing, equivalent to ``parser_for(locales.get("ru"))``.

Shipped packs
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Code
     - Turns on
   * - ``ja``
     - Japanese segmentation — activates division for unspaced
       Japanese names, which needs a segmenter to act: install
       ``nameparser[ja]`` and pass
       ``parser_for(locales.JA, segmenter=locales.ja_segmenter())``
       (``山田太郎`` → family ``山田``, given ``太郎``). The pack ships
       no surname list, because no list divides a kanji name, and no
       order: a Japanese name already reads family-first by default.
   * - ``ru``
     - East Slavic patronymic order — detects the formal
       family/given/patronymic shape (three name words, the last ending
       like a patronymic — Cyrillic and transliterated
       ``-ovich``/``-ovna``-style endings — and the middle not) and
       assigns it accordingly. A middle name with the ending fills
       ``patronymic`` too (``Ivan Ivanovich Ivanov`` → middle and
       patronymic ``Ivanovich``).
   * - ``tr_az``
     - Turkic patronymic markers — detects a name of four words ending
       in a standalone marker token (``oglu``, ``qizi``, ``uulu``, and
       their Latin- and Cyrillic-script variants) and reads its first
       word as the family name (``Aliyev Ilham Heydar oglu`` → family
       ``Aliyev``). A marker and the name before it fill
       ``patronymic`` (``Heydar oglu`` there).
   * - ``zh``
     - Chinese surname segmentation — splits an unspaced Han name into
       surname and given name (``毛泽东`` → family ``毛``, given
       ``泽东``) against the surname list the pack ships. It sets no
       name order: native-script Han already reads family-first
       without a pack. The list holds the commonest surnames of the
       mainland and Taiwan, in both scripts, and the compound surnames
       still borne; a name whose surname is not on it stays whole. A
       Japanese name read with it can split after its first character
       (``安藤一郎`` → family ``安``), so use ``ja`` for Japanese data.

``ja``, ``ru`` and ``tr_az`` are policy-only — they carry no vocabulary
of their own. ``zh`` is both halves at once: a surname list, plus the
one policy field that turns segmentation on for the script it covers. See
:ref:`config-containers` for how that split (language vocabulary vs. behavior)
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

A declared family-first ``name_order`` stands down both patronymic
rotations (``ru`` and ``tr_az``) instead of competing with them. Under
``FAMILY_FIRST`` the two never disagree on a name the rule matches: that
order already reads ``"Сидоров Иван Петрович"`` as family ``Сидоров``,
so folding the pack onto a base built with it adds nothing. Under
``FAMILY_FIRST_GIVEN_LAST`` the declared order wins, and the last
word — the patronymic, or a separate ``oglu``/``qizi`` marker — reads
as the given name. ``patronymic`` does not stand down, but it reads only
a middle name with the ending, so it follows the order: under
``FAMILY_FIRST`` ``Ivan Ivanovich Ivanov`` reads given ``Ivanovich``
and no patronymic. A marker and the word before it are read under
every order.

.. _segmenter-contract:

Segmenters
-----------

``ja`` is policy-only in a second sense: it turns division on for
Japanese text without supplying anything to divide with. That job goes
to a **segmenter**, which is passed to
:func:`~nameparser.parser_for` rather than carried by the pack — a
:class:`~nameparser.Locale` is pure data, and a third-party callable is
neither pure nor data. :func:`~nameparser.locales.ja_segmenter` is the
shipped one; writing your own is worth it for any script whose
divisions you know better than a surname list does.

A :data:`~nameparser.Segmenter` is any callable taking a token's text
and returning a :class:`~nameparser.Segmentation` — the interior
offsets to cut at, plus how confident you are — or ``None`` to decline,
leaving the token whole. Declining is the load-bearing half of the
contract, because ``segment_scripts`` unions across packs: your
segmenter may be offered a token of any activated script, not only the
ones its own pack turned on. It is asked only where the surname list
could not divide an unspaced token, and not where the name is already
divided — by a second word in an East Asian script (the nakaguro ・
counts as a space), a family comma or a 间隔号. A word in any other
script beside the token — Latin (``"Dr. 高橋一郎"``), Cyrillic — divides
nothing, so the segmenter is still asked. Halfwidth katakana counts as
katakana, so ``"高橋一郎 ﾀﾛｳ"`` is already divided. Recognize the text
you can actually read and return ``None`` for the rest, rather than
answering for a script you never meant to handle. A segmenter is your
code, so its failures do not stay inside the parse: its own exceptions
propagate out of ``parse()``, and an answer of the wrong type or a cut
outside the token raises ``TypeError`` or ``ValueError``.

The pack half of that arrangement carries no words at all, which makes
it the shortest kind of pack there is:

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, Script
    >>> script_pack = Locale(code="myscript", lexicon=Lexicon.empty(),
    ...               policy=PolicyPatch(
    ...                   segment_scripts=frozenset({Script.HAN})))

``nameparser/locales/ja.py`` is the shipped example of exactly that
shape: activation is the pack's entire contribution. Applied without a
segmenter it divides nothing, and building the parser emits a
``UserWarning`` naming the scripts that can never divide and the
argument to pass.

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

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, parser_for
    >>> kapitan_lex = Lexicon.empty().add(titles={"kapitan"})
    >>> corp_pack = Locale(code="mycorp", lexicon=kapitan_lex,
    ...                     policy=PolicyPatch(middle_as_family=True))
    >>> kapitan = parser_for(corp_pack).parse("Kapitan Anna Maria Schmidt")
    >>> kapitan.title, kapitan.given, kapitan.family
    ('Kapitan', 'Anna', 'Maria Schmidt')

That pack does two things at once: the :class:`~nameparser.Lexicon`
fragment teaches the parser that ``kapitan`` is a title, and the
:class:`~nameparser.PolicyPatch` turns on ``middle_as_family`` so any
remaining given-position words after the first fold into ``family``
instead of ``middle`` — compare this to the default parser's reading
of the same string, which has no title and splits ``given='Kapitan'``,
``middle='Anna Maria'``, ``family='Schmidt'``.

The lexicon fragment is validated on its own
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``policy`` half is a patch, but the ``lexicon`` half is not. A
pack's :class:`~nameparser.Lexicon` is a complete value in its own
right and is validated on its own, before it is unioned onto the base
— so a fragment listing a word in ``particles_ambiguous``,
``suffix_acronyms_ambiguous``, ``honorific_tails`` or
``suffix_words_ambiguous`` must also list it in the set that field marks
(``particles``, ``suffix_acronyms``, ``suffix_words``). A fragment holding ``particles_ambiguous={"van"}``
without ``particles={"van"}`` raises ``ValueError`` before any union
happens. ``given_name_titles``, ``conjunctions_ambiguous``,
``after_given_titles`` and ``agnomens`` are not checked this way, and can mark a word only the base holds. ``zh`` is the
shipped worked example: its ``Lexicon(surnames=...)`` has to satisfy
every ``Lexicon`` rule standing alone, before anything unions it onto
the base.

Contributing a pack to nameparser
----------------------------------

Shipping a pack in nameparser itself (rather than keeping it local to
your own code) means meeting the in-repo contract, checked mechanically
by ``tests/v2/test_locales.py``:

#. Add a registry entry in ``nameparser/locales/__init__.py`` — a
   ``"CODE": ("module.path", "ATTR")`` row in ``_REGISTRY``, so the
   pack loads lazily on first access (importing ``nameparser.locales``
   never imports pack modules).
#. Write the rules the pack turns on as data, if they are ``Policy``
   fields the vocabulary files' ``[rules]`` table lists
   (``patronymic_rules``, ``name_order``, ``two_family_names``): put the
   table in the pack's language file, list the file in ``PACK_RULES``
   in ``tools/vocab/build.py``, rebuild, and give the pack
   ``policy=rules_patch("<tag>")`` from ``nameparser._locale``, as
   ``ru`` and ``tr_az`` do. ``nameparser/vocab/README.md``'s "Rules"
   section lists the keys. A rule the table does not list is a change
   to the parser, not to a pack.
#. Declare a module-level ``DEVIATES(name)`` predicate: given a name
   string, return whether *this pack alone* might parse it differently
   from the default parser. Over-declaring is safe; under-declaring is
   not — when in doubt, ``DEVIATES`` should say yes. A pack whose
   scope is a *script* builds the predicate with ``_script_matcher``
   from ``nameparser/_policy.py``, the way ``zh`` and ``ja`` do —
   never by compiling its own character ranges: the factory's
   docstring explains how the pack-contract test enforces this.
#. Add a rotator list to ``tests/v2/test_locales.py``. Every pack needs
   one, but what it has to contain follows from how the pack declares
   its scope:

   - **By marker regex** (``ru``, ``tr_az``): at least one name
     exercising every alternation branch of every regex it defines —
     ``test_rotators_cover_every_marker_branch`` fails until each
     branch is hit.
   - **By codepoint range** (``zh``, ``ja``): there are no branches to
     sweep, so the pack drops out of that test and its rotators carry
     the same weight by hand — the unspaced names the pack must split,
     one per shape of the vocabulary it ships: single surname, compound
     surname, and any spelling variant it means to cover.
   - **With no vocabulary at all**: list the shapes its *segmenter* must
     divide instead, and mark the rotator tests to skip when the
     optional dependency is absent, so the contract tests still run
     everywhere.
#. Keep the non-interference gate green over the shared corpus plus
   your rotators: every name the packed parser parses differently from
   the default must be one your ``DEVIATES`` predicate flags — no
   silent, undeclared side effects on names outside the pack's stated
   scope.
#. Decide which layer the vocabulary belongs in, if the pack carries
   any. Vocabulary that is *self-selecting* — able to match only text of
   the tradition it came from, the way a hangul surname can only ever
   match hangul — is default-safe, and belongs in the default lexicon
   (``nameparser/vocab/*.toml``; a segmentation surname list such as
   ``config/surnames.py`` stays in ``nameparser/config/``) rather than in
   a pack: a pack nobody knows
   to ask for is vocabulary nobody gets. Vocabulary that *declares a
   language its script does not* — a Chinese surname list, which
   silently mangles the Japanese names written in the same characters
   — belongs in the pack, where asking for it is the declaration.
   ``ja``, ``ru`` and ``tr_az`` need no vocabulary at all and ship an
   empty :class:`~nameparser.Lexicon`; ``nameparser/locales/zh.py`` is
   the template for one that does.
#. Curate vocabulary conservatively, the same rule as
   :ref:`ambiguous-words`: when you're unsure whether a word or a
   marker belongs, leave it out.

``nameparser/locales/ru.py`` is the reference implementation for a
policy-only pack, ``nameparser/locales/zh.py`` for one that carries
vocabulary, and ``nameparser/locales/ja.py`` for one whose whole
contribution is turning a stage on. Packs still in progress are
tracked in issue `#345
<https://github.com/derek73/python-nameparser/issues/345>`_ (``hi``
and ``bn``).
