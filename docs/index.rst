.. Nameparser documentation master file, created by
   sphinx-quickstart on Fri May 16 01:29:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

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

Coming from 1.x? :doc:`migrate`.

.. toctree::
   :maxdepth: 2

   usage
   concepts
   customize
   locales
   migrate
   modules
   release_log
   resources
   contributing

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


**GitHub Project**: https://github.com/derek73/python-nameparser
