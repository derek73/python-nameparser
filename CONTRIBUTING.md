Contributing
==============

Development Environment Setup
--------------------------------

Install dev dependencies (requires pip >= 24.1 for dependency group support):

    pip install --group dev

Running Tests
---------------

    python tests.py

You can also pass a name string to `tests.py` to see how it will be parsed:

    $ python tests.py "Secretary of State Hillary Rodham-Clinton"
    <HumanName : [
    	Title: 'Secretary of State' 
    	First: 'Hillary' 
    	Middle: '' 
    	Last: 'Rodham-Clinton' 
    	Suffix: ''
    ]>

CI runs tests against Python 3.10–3.13 via GitHub Actions on every push and pull request.

Writing Tests
----------------

If you make changes, please include tests with example names that should parse correctly.

It's a good idea to include tests of alternate comma placement formats of the name to ensure that the 3 code paths for the 3 formats work in the same way.

Unless you add better coverage someplace else, add a few examples of your names to `TEST_NAMES`. A test attempts to try the 3 different comma variations of these names automatically and make sure things don't blow up, so it can be a helpful regression indicator.

New Releases
------------

    $ python -m build
    $ twine upload dist/*
