Contributing
============

The project is hosted on GitHub:

https://github.com/derek73/python-nameparser

Find more information about running tests and contributing the project at the projects contribution guide.

https://github.com/derek73/python-nameparser/blob/master/CONTRIBUTING.md

.. _contributing-a-pack:

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
   (``patronymic_rules``, ``name_order``, ``two_family_names``,
   ``two_given_names``, ``initials_as_family``): put the
   table in the pack's language file, list the file in ``PACK_RULES``
   in ``tools/vocab/build.py``, rebuild, and give the pack
   ``policy=rules_patch("<tag>")`` from ``nameparser._locale``, as
   ``ru``, ``tr_az``, ``es``, ``cs``, ``sk``, ``vi``, ``ne`` and ``mn`` do. ``nameparser/vocab/README.md``'s "Rules"
   section lists the keys. A rule the table does not list is a change
   to the parser, not to a pack.
#. Declare a module-level ``DEVIATES(name)`` predicate. Given a name
   string, ``DEVIATES`` returns whether *this pack alone* might parse
   it differently from the default parser. Over-declaring is safe; under-declaring is
   not — when in doubt, ``DEVIATES`` should say yes. A pack whose
   scope is a *script* builds the predicate with ``_script_matcher``
   from ``nameparser/_policy.py``, the way ``zh`` and ``ja`` do —
   never by compiling its own character ranges: the factory's
   docstring explains how the pack-contract test enforces this. A
   pack's choice of languages is never declared: its deviations are
   derived from the words the choice changes, so a pack that is nothing
   but a choice (``hi``, ``sl``, ``ga``) declares no ``DEVIATES`` — the
   contract test refuses one, and refuses a choice that changes no
   word — and one with a fragment or a patch beside its choice
   declares only what those change.
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
   - **By a choice of languages** (``ne``, ``hi``, ``bn``, ``cs``, ``sk``,
     ``sl``, ``hr``, ``ga``, ``gd``, ``es``, ``es_ar``, ``pt``, ``pt_br``, ``vi``, and ``ja``'s 君): a name for each word the choice changes, in each script it
     is written in and each position where the default reads it
     otherwise — ``test_choice_rotators_cover_every_changed_word`` fails
     until every word is held. A pack whose choice changes no word
     beside a patch that does (``mn``, whose file's readings are all on
     by default) has no word to hold: list it in the test file's
     ``_INERT_CHOICES``, and its rotators cover what the patch moves.
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
   the Korean one, in ``nameparser/config/_ko_surnames.py``, is read as
   ``Lexicon.default().surnames``) rather than in
   a pack: a pack nobody knows
   to ask for is vocabulary nobody gets. Vocabulary that *declares a
   language its script does not* — a Chinese surname list, which
   silently mangles the Japanese names written in the same characters
   — belongs in the pack, where asking for it is the declaration.
   ``ja``, ``ru`` and ``tr_az`` need no vocabulary list of their own and ship an
   empty :class:`~nameparser.Lexicon`; ``nameparser/locales/zh.py`` is
   the template for one that does.
#. Curate vocabulary conservatively, the same rule as
   :ref:`ambiguous-words`: when you're unsure whether a word or a
   marker belongs, leave it out.

``nameparser/locales/ru.py`` is the reference implementation for a
policy-only pack, ``nameparser/locales/zh.py`` for one that carries
vocabulary, and ``nameparser/locales/ja.py`` for one whose main
contribution is turning a stage on.
