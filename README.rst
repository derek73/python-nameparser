Name Parser
===========

|Build Status| |PyPI| |PyPI version| |Documentation| |License| |Downloads| |Codecov|

A simple Python (3.10+) module for parsing human names into their
individual components. 

* hn.title
* hn.first
* hn.middle
* hn.last
* hn.suffix
* hn.nickname
* hn.maiden
* hn.surnames *(middle + last)*
* hn.given_names *(first + middle)*
* hn.initials *(first initial of each name part)*
* hn.last_base *(last, minus any prefixes)*
* hn.last_prefixes *(leading last-name particles, e.g. "van der")*

Supported Name Structures
~~~~~~~~~~~~~~~~~~~~~~~~~

The supported name structure is generally "Title First Middle Last Suffix", where all pieces 
are optional. Comma-separated format like "Last, First" is also supported.

1. Title Firstname "Nickname" Middle Middle Lastname Suffix
2. Lastname [Suffix], Title Firstname (Nickname) Middle Middle[,] Suffix [, Suffix]
3. Title Firstname M Lastname [Suffix], Suffix [Suffix] [, Suffix]

How It Works
~~~~~~~~~~~~

The parser works in two layers.

A **vocabulary layer** recognizes name pieces by what they are, using
configurable sets of known words: titles ("Dr."), suffixes ("III", "PhD"),
last-name prefixes ("de la"), conjunctions ("y", "&"), and delimited
nicknames ("Doc"). Titles and conjunctions chain together to handle complex
titles like "Asst Secretary of State"; prefixes join forward so "de la Vega"
stays one last name. This layer doesn't care where in the string a word
appears — and it's the layer you customize, by adding or removing entries
in the sets to fit your dataset.

A **positional layer** then assigns everything the vocabulary layer didn't
claim, based purely on where it sits: the first unclaimed word is the first
name, the last one is the last name, and anything between them is a middle
name. There is no semantic understanding — "Dr" is a title when it comes
before a name and a suffix when it comes after ("pre-nominal" and
"post-nominal" would probably be better names) — and no attempt to correct
mistakes in the input.

It attempts the best guess that can be made with a simple, deterministic,
rule-based approach — no statistical models or machine learning; the same
input always parses the same way. The positional layer assumes Western name
order (given name first), so the main use case is English and other
languages that share that structure. It can also try to correct the
capitalization of names that are all upper- or lowercase. It's not perfect,
but it gets you pretty far.

Installation
------------

::

  pip install nameparser

If you want to try out the latest code from GitHub you can
install with pip using the command below.

``pip install -e git+https://github.com/derek73/python-nameparser.git``

If you need to handle lists of names, check out
`namesparser <https://github.com/gwu-libraries/namesparser>`_, a
compliment to this module that handles multiple names in a string.


Quick Start Example
-------------------

::

    >>> from nameparser import HumanName
    >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III (Doc Vega)")
    >>> name 
    <HumanName : [
        title: 'Dr.'
        first: 'Juan'
        middle: 'Q. Xavier'
        last: 'de la Vega'
        suffix: 'III'
        nickname: 'Doc Vega'
        maiden: ''
    ]>
    >>> name.last
    'de la Vega'
    >>> name.as_dict()
    {'title': 'Dr.', 'first': 'Juan', 'middle': 'Q. Xavier', 'last': 'de la Vega', 'suffix': 'III', 'nickname': 'Doc Vega', 'maiden': ''}
    >>> str(name)
    'Dr. Juan Q. Xavier de la Vega III (Doc Vega)'
    >>> name.string_format = "{first} {last}"
    >>> str(name)
    'Juan de la Vega'


Because the positional layer has no semantic understanding, position is
everything:

::

    >>> name = HumanName("1 & 2, 3 4 5, Mr.")
    >>> name 
    <HumanName : [
        title: ''
        first: '3'
        middle: '4 5'
        last: '1 & 2'
        suffix: 'Mr.'
        nickname: ''
        maiden: ''
    ]>

Customization
-------------

Your project may need some adjustment for your dataset. Most customization
is vocabulary — `customizing the configured pre-defined sets`_ of titles,
prefixes, etc. that the vocabulary layer matches against. You can also do
your own pre- or post-processing, or subclass the `HumanName` class for
deeper changes. See the `full documentation`_ for more information.


`Full documentation`_
~~~~~~~~~~~~~~~~~~~~~

.. _customizing the configured pre-defined sets: http://nameparser.readthedocs.org/en/latest/customize.html
.. _Full documentation: http://nameparser.readthedocs.org/en/latest/


Contributing
------------

If you come across name piece that you think should be in the default config, you're
probably right. `Start a New Issue`_ and we can get them added. 

Please let me know if there are ways this library could be structured to make
it easier for you to use in your projects. Read CONTRIBUTING.md_ for more info
on running the tests and contributing to the project.

**GitHub Project**

https://github.com/derek73/python-nameparser

.. _CONTRIBUTING.md: https://github.com/derek73/python-nameparser/tree/master/CONTRIBUTING.md
.. _Start a New Issue: https://github.com/derek73/python-nameparser/issues
.. _click here to propose changes to the titles: https://github.com/derek73/python-nameparser/edit/master/nameparser/config/titles.py

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
