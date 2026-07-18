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

.. autodata:: nameparser.UNSET

.. autoclass:: nameparser.PatronymicRule
   :members:

.. autodata:: nameparser.GIVEN_FIRST

.. autodata:: nameparser.FAMILY_FIRST

.. autodata:: nameparser.FAMILY_FIRST_GIVEN_LAST

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
