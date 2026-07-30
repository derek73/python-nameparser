API reference
=============

The 2.0 API
-----------

Parsing
~~~~~~~

.. autofunction:: nameparser.parse

.. autoclass:: nameparser.Parser
   :members:

.. autofunction:: nameparser.parser_for

.. autoclass:: nameparser.Segmentation
   :members:

.. py:data:: nameparser.Segmenter
   :value: Callable[[str], Segmentation | None]

   The type of the optional ``Parser(segmenter=...)`` hook: a callable
   given one token's text, returning a
   :class:`~nameparser.Segmentation` that divides it, or ``None`` to
   decline and leave it whole. An alias, not a class — any callable of
   that shape qualifies, and nothing needs to be subclassed or
   registered. It is consulted only for tokens whose script is listed
   in :attr:`Policy.segment_scripts
   <nameparser.Policy.segment_scripts>`, and only where the surname
   vocabulary declined first; see :ref:`segmenter-contract` for what a
   segmenter owes its caller.
   :func:`~nameparser.locales.ja_segmenter` is the shipped
   implementation.

Results
~~~~~~~

.. autoclass:: nameparser.ParsedName
   :members:

.. autoclass:: nameparser.Token
   :members:

.. py:data:: nameparser.STABLE_TAGS
   :value: frozenset({"particle", "conjunction", "initial", "joined"})

   The four :attr:`Token.tags <nameparser.Token.tags>` values that are
   stable API: ``particle`` (a word from the particle vocabulary,
   "de"/"van", wherever it lands — combine with ``Role.FAMILY`` for
   actual family particles),
   ``conjunction`` (a joining word, "and"/"y"), ``initial`` (an
   initial-shaped word, "J."), and ``joined`` (a continuation of the
   previous token within one merged piece, so the suffix view renders
   "Ph. D." as one credential). Every other tag is namespaced
   (``vocab:...``) and unstable — never match against those.

.. autoclass:: nameparser.Span
   :members:

.. autoclass:: nameparser.Role
   :members:

.. autoclass:: nameparser.Ambiguity
   :members:

.. autoclass:: nameparser.AmbiguityKind
   :members:

Configuration
~~~~~~~~~~~~~

.. autoclass:: nameparser.Lexicon
   :members:

.. autoclass:: nameparser.Policy
   :members:

.. autoclass:: nameparser.PolicyPatch
   :members:

.. py:data:: nameparser.UNSET

   Sentinel meaning "this patch does not set this field" — the default
   of every :class:`~nameparser.PolicyPatch` field, distinguishable
   from every real value including ``None`` and ``False``. You rarely
   need it: omit a field instead of passing it. Import it to test
   whether a patch sets a field (``patch.name_order is UNSET``) or to
   leave a field conditionally unset when building patches
   programmatically.

.. autoclass:: nameparser.PatronymicRule
   :members:

.. autoclass:: nameparser.Script
   :members:

.. _name-order-constants:

Name-order constants
^^^^^^^^^^^^^^^^^^^^

The three valid values for ``Policy(name_order=...)``. ``name_order``
is deliberately restricted to these exported constants — an arbitrary
tuple of :class:`~nameparser.Role` members raises ``ValueError``,
because only these three orders have defined assignment semantics.

.. py:data:: nameparser.GIVEN_FIRST
   :value: (Role.GIVEN, Role.MIDDLE, Role.FAMILY)

   Western order (the default): the first word of positional input is
   the given name, the last is the family name, everything between is
   middle.

.. py:data:: nameparser.FAMILY_FIRST
   :value: (Role.FAMILY, Role.GIVEN, Role.MIDDLE)

   Family name first, given name second, remaining words middle —
   e.g. Hungarian, or East Asian order.

.. py:data:: nameparser.FAMILY_FIRST_GIVEN_LAST
   :value: (Role.FAMILY, Role.MIDDLE, Role.GIVEN)

   Family name first, given name *last*, the words between middle —
   e.g. Vietnamese full-name order.

.. py:data:: nameparser.DEFAULT_SCRIPT_ORDERS
   :value: ((Script.HAN, FAMILY_FIRST), (Script.HANGUL, FAMILY_FIRST), (Script.HIRAGANA, FAMILY_FIRST))

   The default :attr:`~nameparser.Policy.script_orders` table: a name
   written wholly in Han or Hangul reads family-first, and so does a
   Japanese name mixing kanji with kana, which resolves to the
   ``HIRAGANA`` entry whichever of the two syllabaries it actually
   uses — that member is the license's carrier key, not a claim about
   the characters present. A name written wholly in katakana has no
   entry on purpose and stays positional. A matching
   entry in this table takes precedence over ``name_order``, including
   a ``name_order`` you set explicitly — ``name_order`` governs only
   the names no entry matches. The values are drawn from the same
   three constants above, and the same restriction applies. Build on it for
   additive customization —
   ``script_orders=dict(DEFAULT_SCRIPT_ORDERS) | {Script.HAN:
   GIVEN_FIRST}`` — and pass ``script_orders={}`` to opt out entirely
   and get the purely positional read back. Latin-script and
   mixed-script names are never affected either way.

Delimiter defaults
^^^^^^^^^^^^^^^^^^

.. py:data:: nameparser.DEFAULT_NICKNAME_DELIMITERS
   :value: frozenset({("'", "'"), ('"', '"'), ("(", ")"), ("“", "”"), ("„", "“"), ("”", "”"), ("«", "»"), ("»", "«"), ("「", "」"), ("『", "』"), ("（", "）")})

   The default :attr:`~nameparser.Policy.nickname_delimiters` set:
   straight quotes and parentheses plus the typographic conventions —
   smart quotes, German/Polish low-high quotes, Swedish right-right
   quotes, guillemets in both directions, CJK corner brackets, and
   fullwidth parentheses (#273). Curly *single* quotes are deliberately
   absent: U+2019 is the typographic apostrophe ("O’Connor"). Build on
   the constant for additive customizations, e.g.
   ``nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("｟", "｠")}``;
   to *reroute* a pair to ``maiden``, just list it in
   :attr:`~nameparser.Policy.maiden_delimiters` (it is dropped from
   the effective nickname set automatically).

Locales
~~~~~~~

.. autoclass:: nameparser.Locale
   :members:

.. automodule:: nameparser.locales
   :members: get, available

.. autofunction:: nameparser.locales.ja_segmenter

1.x compatibility layer
------------------------

.. note::

   ``HumanName`` and ``nameparser.config`` are the 1.x API, kept
   working through 2.x and removed in 3.0. New code should use the
   2.0 API above; see :doc:`migrate`.

HumanName.parser
~~~~~~~~~~~~~~~~

.. py:module:: nameparser.parser

.. py:class:: HumanName
   :noindex:

.. autoclass:: HumanName
   :members:
   :special-members: __eq__, __init__

HumanName.config
~~~~~~~~~~~~~~~~

.. automodule:: nameparser.config
   :members:

HumanName.config Defaults
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: nameparser.config.titles
   :members:
.. automodule:: nameparser.config.suffixes
   :members:
.. automodule:: nameparser.config.prefixes
   :members:
.. automodule:: nameparser.config.bound_first_names
   :members:
.. automodule:: nameparser.config.conjunctions
   :members:
.. automodule:: nameparser.config.maiden_markers
   :members:
.. automodule:: nameparser.config.surnames
   :members:
.. automodule:: nameparser.config.capitalization
   :members:
.. automodule:: nameparser.config.regexes
   :members:
