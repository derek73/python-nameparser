Python Human Name Parser
========================

Version |release|

nameparser parses human names into seven fields — title, given,
middle, family, suffix, nickname, maiden. Results are immutable,
configuration is composable (:class:`~nameparser.Lexicon` for
vocabulary, :class:`~nameparser.Policy` for behavior), and locale
packs are opt-in. Requires Python 3.11+.

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.given, name.family
    ('Juan', 'de la Vega')
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'

New here? :doc:`getting-started` takes you through the three steps
most people need:

- **Parse one name** into its fields, as above.
- **Have a list of names from one source?** :doc:`suggest` reads the
  order it is written in and returns a parser configured for it.
- **Joining records from several sources?** :doc:`matching` groups the
  names and compares them field by field.

Coming from 1.x, or from 2.x code using ``HumanName``? :doc:`migrate`.

.. toctree::
   :maxdepth: 2
   :caption: Start here

   getting-started

.. toctree::
   :maxdepth: 2
   :caption: Reading names

   usage
   shapes
   east-asian

.. toctree::
   :maxdepth: 2
   :caption: Lists of names

   suggest
   matching

.. toctree::
   :maxdepth: 2
   :caption: Configuring

   customize
   policy
   locales
   languages

.. toctree::
   :maxdepth: 1
   :caption: Background and reference

   concepts
   modules
   migrate
   release_log
   contributing

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


**GitHub Project**: https://github.com/derek73/python-nameparser
