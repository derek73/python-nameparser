A simple Python module for parsing human names into their individual components.

Components::

    * Title
    * First name
    * Middle names
    * Last names
    * Suffixes

Works for a variety of common name formats for latin-based languages. Over 
100 unit tests with example names. Should be unicode safe but it's fairly untested.

HumanName instances will pass an equals (==) test if their lower case unicode
representations are the same.
