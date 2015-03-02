Release Log
===========

* 0.3.4 - March 1, 2015
    - Fix #24, handle first name also a prefix
    - Fix #26, last name comma format when lastname is also a title
* 0.3.3 - Aug 4, 2014
    - Allow suffixes to be chained (#8)
    - Handle trailing suffix in last name comma format (#3). Removes support for titles
    with periods but no spaces in them, e.g. "Lt.Gen.". (#21)
* 0.3.2 - July 16, 2014
    - Retain original string in "original" attribute.
    - Collapse white space when using custom string format.
    - Fix #19, single comma name format may have trailing suffix
* 0.3.1 - July 5, 2014
    - Fix Pypi package, include new config module.
* 0.3.0 - July 4, 2014
    - Refactor configuration to simplify modifications to constants (backwards incompatible)
    - use unicode_literals to simplify Python 2 & 3 support.
    - Generate documentation using sphinx and host on readthedocs.
* 0.2.10 - May 6, 2014
    - If name is only a title and one part, assume it's a last name instead of a first name, with exceptions for some titles like 'Sir'. (`#7 <https://github.com/derek73/python-nameparser/issues/7>`_).
    - Add some judicial and other common titles. (#9) 
* 0.2.9 - Apr 1, 2014
    - Add a new nickname attribute containing anything in parenthesis or double quotes (`Issue 33 <https://code.google.com/p/python-nameparser/issues/detail?id=33>`_).
* 0.2.8 - Oct 25, 2013
    - Add support for Python 3.3+. Thanks to @corbinbs.
* 0.2.7 - Feb 13, 2013
    - Fix bug with multiple conjunctions in title
    - add legal and crown titles
* 0.2.6 - Feb 12, 2013
    - Fix python 2.6 import error on logging.NullHandler
* 0.2.5 - Feb 11, 2013
    - Set logging handler to NullHandler
    - Remove 'ben' from PREFIXES because it's more common as a name than a prefix.
    - Deprecate BlankHumanNameError. Do not raise exceptions if full_name is empty string. 
* 0.2.4 - Feb 10, 2013
    - Adjust logging, don't set basicConfig. Fix `Issue 10 <https://code.google.com/p/python-nameparser/issues/detail?id=10>`_ and `Issue 26 <https://code.google.com/p/python-nameparser/issues/detail?id=26>`_.
    - Fix handling of single lower case initials that are also conjunctions, e.g. "john e smith". Re `Issue 11 <https://code.google.com/p/python-nameparser/issues/detail?id=11>`_.
    - Fix handling of initials with no space separation, e.g. "E.T. Jones". Fix #11.
    - Do not remove period from first name, when present.
    - Remove 'e' from PREFIXES because it is handled as a conjunction.
    - Python 2.7+ required to run the tests. Mark known failures.
    - tests/test.py can now take an optional name argument that will return repr() for that name.
* 0.2.3 - Fix overzealous "Mac" regex
* 0.2.2 - Fix parsing error
* 0.2.0 
    - Significant refactor of parsing logic. Handle conjunctions and prefixes before
      parsing into attribute buckets.
    - Support attribute overriding by assignment.
    - Support multiple titles. 
    - Lowercase titles constants to fix bug with comparison. 
    - Move documentation to README.rst, add release log.
* 0.1.4 - Use set() in constants for improved speed. setuptools compatibility - sketerpot
* 0.1.3 - Add capitalization feature - twotwo
* 0.1.2 - Add slice support

