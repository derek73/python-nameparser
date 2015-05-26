Name Parser
===========

.. image:: https://travis-ci.org/derek73/python-nameparser.svg?branch=master
   :target: https://travis-ci.org/derek73/python-nameparser
.. image:: https://badge.fury.io/py/nameparser.svg
    :target: http://badge.fury.io/py/nameparser

A simple Python module for parsing human names into their individual
components. The HumanName class splits a name string up into name parts
based on placement in the string and matches against known name pieces
like titles. It joins name pieces on conjunctions and special prefixes to
last names like "del". Titles can be chained together and include conjunctions
to handle titles like "Asst Secretary of State". It can also try to 
correct capitalization of all upper or lowercase names.

It attempts the best guess that can be made with a simple, rule-based
approach. It's not perfect, but it gets you pretty far.

**Quick Start Example**

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
    u'de la Vega'
    >>> name.as_dict()
    {u'last': u'de la Vega', u'suffix': u'III', u'title': u'Dr.', u'middle': u'Q. Xavier', u'nickname': u'Doc Vega', u'first': u'Juan'}


Supports 3 different comma placement variations typically used for names of people.

* Title Firstname "Nickname" Middle Middle Lastname Suffix
* Lastname [Suffix], Title Firstname (Nickname) Middle Middle[,] Suffix [, Suffix]
* Title Firstname M Lastname [Suffix], Suffix [Suffix] [, Suffix]

Unit Tests
------------

Over 200 unit tests with example names. `Start a New Issue`_ 
for names that fail and I will try to fix it. 


Installation
------------

``pip install nameparser``

I usually push changes to `PyPi <https://pypi.python.org/pypi/nameparser>`_
pretty quickly. If you want to try out the latest code from GitHub you can
install with pip using the command below.

``pip install -e git+git://github.com/derek73/python-nameparser.git#egg=nameparser``

If you're looking for a web service, check out
`eyeseast's nameparse service <https://github.com/eyeseast/nameparse>`_, a
simple Heroku-friendly Flask wrapper for this module.


Documentation
-------------

http://nameparser.readthedocs.org/en/latest/

**NOTE:** This documentation covers the new **version 0.3**. For the v0.2.10 documentation,
see the `v0.2.10 tag`_ on GitHub.

.. _v0.2.10 tag: https://github.com/derek73/python-nameparser/tree/v0.2.10



Contributing
------------

If you come across name piece that you think should be in the default config, you're
probably right. `Start a New Issue`_ and we can get them added. 

Or, use GitHub's nifty
web interface to add your new pieces directly to the config files and create a pull
request all in one go, no fork needed. As an example, `click here to propose changes to
the titles`_ config.

Please let me know if there are ways this library could be restructured to make
it easier for you to use in your projects. Read CONTRIBUTING.md_ for more info
on running the tests and contributing to the project.

**GitHub Project**

https://github.com/derek73/python-nameparser

.. _CONTRIBUTING.md: https://github.com/derek73/python-nameparser/tree/master/CONTRIBUTING.md
.. _Start a New Issue: https://github.com/derek73/python-nameparser/issues
.. _click here to propose changes to the titles: https://github.com/derek73/python-nameparser/edit/master/nameparser/config/titles.py