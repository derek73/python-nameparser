Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

nameparser parses human names into seven fields — title, given, middle,
family, suffix, nickname, maiden. Results are immutable, configuration is
composable, and locale packs are opt-in.

Installation
------------

::

  pip install nameparser

Requires Python 3.11+.

Quick Start Example
--------------------

.. code-block:: python

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.given, name.family
    ('Juan', 'de la Vega')
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'

Those seven fields are ``title``, ``given``, ``middle``, ``family``,
``suffix``, ``nickname``, and ``maiden`` — plus aggregate views like
``given_names``, ``surnames``, ``family_base``, and ``family_particles``
for combining or splitting them further.

Learn more
----------

* `Getting started <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — the full tour: parsing, aggregates, dicts, rendering, dedup
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ — vocabulary, behavior, and presentation
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, and more
* There's also a CLI: ``python -m nameparser --json "Doe, John"``

Coming from 1.x
----------------

Nothing breaks. 2.0 keeps ``HumanName`` and ``CONSTANTS`` working exactly
as before — same imports, same attributes, same mutation API. See
`Migrating from HumanName <https://nameparser.readthedocs.io/en/latest/migrate.html>`__
for translating a v1 customization into the new API, whenever that's
convenient for you.

See the `release log <https://nameparser.readthedocs.io/en/latest/release_log.html>`__
for the full list of changes in the 2.0 series.

License
-------

LGPL licensed. See `LICENSE <https://github.com/derek73/python-nameparser/blob/master/LICENSE>`__
for details.

.. |Build Status| image:: https://github.com/derek73/python-nameparser/actions/workflows/python-package.yml/badge.svg
   :target: https://github.com/derek73/python-nameparser/actions/workflows/python-package.yml
.. |PyPI| image:: https://img.shields.io/pypi/v/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |Documentation| image:: https://readthedocs.org/projects/nameparser/badge/?version=latest
   :target: http://nameparser.readthedocs.io/en/latest/?badge=latest
.. |PyPI version| image:: https://img.shields.io/pypi/pyversions/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |License| image:: https://img.shields.io/pypi/l/nameparser.svg
   :target: https://pypi.org/project/nameparser/
.. |Downloads| image:: https://static.pepy.tech/badge/nameparser
   :target: https://pepy.tech/project/nameparser
.. |Codecov| image:: https://codecov.io/gh/derek73/python-nameparser/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/derek73/python-nameparser
