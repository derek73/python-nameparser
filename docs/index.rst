.. Nameparser documentation master file, created by
   sphinx-quickstart on Fri May 16 01:29:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Python Human Name Parser
========================

Version |release| 

A simple Python module for parsing human names into their individual 
components. 

* hn.title
* hn.first
* hn.middle
* hn.last
* hn.suffix
* hn.nickname

Supports 3 different comma placement variations in the input string.

1. Title Firstname "Nickname" Middle Middle Lastname Suffix
2. Lastname [Suffix], Title Firstname (Nickname) Middle Middle[,] Suffix [, Suffix]
3. Title Firstname M Lastname [Suffix], Suffix [Suffix] [, Suffix]


It attempts the best guess that can be made with a simple, rule-based 
approach. It's not perfect, but it gets you pretty far. 

Its main use case is English, but it may be useful for other latin-based languages, especially 
if you are willing to `customize it`_, but it is not likely to be useful for languages 
that do not share the same structure as English names.

.. _customize it: customize.html

Instantiating the `HumanName` class with a string splits on commas and then spaces, 
classifying name parts based on placement in the string and matches against known name 
pieces like titles. It joins name pieces on conjunctions and special prefixes to last names like 
"del". Titles can be chained together and include conjunctions to handle 
titles like "Asst Secretary of State". It can also try to correct 
capitalization.

It does not attempt to correct input mistakes. When there is ambiguity that cannot be resolved by a rule-based approach, 
HumanName prefers to handle the most common cases correctly. For example, 
"Dean" is not parsed as title because it is more common as a first name 
(You can customize this behavior though, see `Parser Customization Examples`_).

.. _Parser Customization Examples: customize.html#parser-customization-examples


Parsing Names
-------------

.. toctree::
   :maxdepth: 2
   
   usage
   customize

**Developer Documentation**

.. toctree::
   :maxdepth: 2
   
   modules
   resources
   release_log
   contributing



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


**GitHub Project**: https://github.com/derek73/python-nameparser

