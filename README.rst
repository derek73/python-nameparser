Name Parser
===========

.. image:: https://travis-ci.org/derek73/python-nameparser.svg?branch=master
   :target: https://travis-ci.org/derek73/python-nameparser
.. image:: https://badge.fury.io/py/nameparser.svg
    :target: http://badge.fury.io/py/nameparser

A simple Python (3.2+ & 2.6+) module for parsing human names into their individual
components. The HumanName class splits a name string up into name parts
based on placement in the string and matches against known name pieces
like titles. It joins name pieces on conjunctions and special prefixes to
last names like "del". Titles can be chained together and include conjunctions
to handle titles like "Asst Secretary of State". It can also try to 
correct capitalization of all upper or lowercase names.

It attempts the best guess that can be made with a simple, rule-based approach. 
Unicode is supported, but the parser is not likely to be useful for languages 
that to not share the same structure as English names. It's not perfect, but it 
gets you pretty far.

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
    ]>
    >>> name.last
    'de la Vega'
    >>> name.as_dict()
    {'last': 'de la Vega', 'suffix': 'III', 'title': 'Dr.', 'middle': 'Q. Xavier', 'nickname': 'Doc Vega', 'first': 'Juan'}
    >>> name.string_format = "{first} {last}"
    >>> str(name)
    'Juan de la Vega'


3 different comma placement variations are supported for the string that you pass.

* Title Firstname "Nickname" Middle Middle Lastname Suffix
* Lastname [Suffix], Title Firstname (Nickname) Middle Middle[,] Suffix [, Suffix]
* Title Firstname M Lastname [Suffix], Suffix [Suffix] [, Suffix]

The parser does not make any attempt to clean the data. It mostly just splits on white
space and puts things in buckets based on their position in the string. This also means
the difference between 'title' and 'suffix' is positional, not semantic. ("Pre-nominal"
and "post-nominal" would probably be better names.)

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
    ]>

Customization
-------------

Your project may need a bit of adjustments for your dataset. You can
do this in your own pre- or post-processing, by `customizing the configured pre-defined 
sets`_ of titles, prefixes, etc., or by subclassing the `HumanName` class. See the 
`full documentation`_ for more information.


`Full documentation`_
~~~~~~~~~~~~~~~~~~~~~

.. _customizing the configured pre-defined sets: http://nameparser.readthedocs.org/en/latest/customize.html
.. _Full documentation: http://nameparser.readthedocs.org/en/latest/


Installation
------------

``pip install nameparser``

If you want to try out the latest code from GitHub you can
install with pip using the command below.

``pip install -e git+git://github.com/derek73/python-nameparser.git#egg=nameparser``

If you're looking for a web service, check out
`eyeseast's nameparse service <https://github.com/eyeseast/nameparse>`_, a
simple Heroku-friendly Flask wrapper for this module.


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