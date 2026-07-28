Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

nameparser parses human names into seven fields — title, given, middle,
family, suffix, nickname, maiden. Results are immutable, configuration is
composable, and locale packs are opt-in.

📣 **nameparser 2.0 is out.** Existing ``HumanName`` code keeps working
through 2.x — most 1.x code needs no changes. The `migration guide
<https://nameparser.readthedocs.io/en/latest/migrate.html>`__ has the
field-by-field map, and anything the migration missed can be reported
on `the discussion issue
<https://github.com/derek73/python-nameparser/issues/284>`__.

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

* `Using the parser <https://nameparser.readthedocs.io/en/latest/usage.html>`__ — the full tour: input shapes, aggregates, rendering, comparison, ambiguities, tokens
* `Customizing the parser <https://nameparser.readthedocs.io/en/latest/customize.html>`__ — vocabulary, behavior, and presentation
* `Locale packs <https://nameparser.readthedocs.io/en/latest/locales.html>`__ — opt-in bundles for East Slavic patronymics, Turkic markers, and more
* There's also a CLI: ``python -m nameparser --json "Doe, John"``

Coming from 1.x
----------------

``HumanName`` and ``CONSTANTS`` keep working in 2.0 — same imports, same
attributes, same mutation API. What 2.0 removes is the batch of
deprecations 1.3 and 1.4 announced, so if your test suite runs clean on
1.4 under ``python -W error::DeprecationWarning``, you are nearly done.
Two things that check will not catch: four removals 1.4 never warned
about (three raise on contact, the fourth only warns), and one that
changes results silently — ``name == "John Smith"`` is now ``False``.
`Migrating from HumanName <https://nameparser.readthedocs.io/en/latest/migrate.html>`__
covers both, and translates a v1 customization into the new API whenever
that's convenient for you.

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
