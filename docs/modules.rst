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

Results
~~~~~~~

.. autoclass:: nameparser.ParsedName
   :members:

.. autoclass:: nameparser.Token
   :members:

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

Delimiter defaults
^^^^^^^^^^^^^^^^^^

.. py:data:: nameparser.DEFAULT_NICKNAME_DELIMITERS
   :value: frozenset({("'", "'"), ('"', '"'), ("(", ")")})

   The default :attr:`~nameparser.Policy.nickname_delimiters` set —
   quotes and parentheses. Build on it for additive customizations,
   e.g. ``nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS |
   {("«", "»")}``; to *reroute* a pair to ``maiden``, just list it in
   :attr:`~nameparser.Policy.maiden_delimiters` (it is dropped from
   the effective nickname set automatically).

Locales
~~~~~~~

.. autoclass:: nameparser.Locale
   :members:

.. automodule:: nameparser.locales
   :members: get, available

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
.. automodule:: nameparser.config.capitalization
   :members:
.. automodule:: nameparser.config.regexes
   :members:
