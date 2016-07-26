Contributing
==============

Development Environment Setup
--------------------------------

There are some exernal dependencies required in order to run the
tests, located in the dev-requirements.txt file.

    pip install -r dev-requirements.txt

If you are running Python 2.6 you will also need to `pip install unitest2`
in order to run the tests.

Travis CI
---------

[![Build Status](https://travis-ci.org/derek73/python-nameparser.svg?branch=master)](https://travis-ci.org/derek73/python-nameparser)

The GitHub project is set up with Travis CI. Tests are run
automatically against new code pushes to any branch in the main
repository. Test results may be viewed here:

https://travis-ci.org/derek73/python-nameparser

Running Tests
---------------

To run the tests locally, run `python tests.py`.


    python tests.py


You can also pass a name string to `tests.py` to see how it will be parsed.

    $ python tests.py "Secretary of State Hillary Rodham-Clinton"
    <HumanName : [
    	Title: 'Secretary of State' 
    	First: 'Hillary' 
    	Middle: '' 
    	Last: 'Rodham-Clinton' 
    	Suffix: ''
    ]>


Writing Tests
----------------

If you make changes, please make sure you include tests with example
names that you want to be parsed correctly.

It's a good idea to include tests of alternate comma placement formats
of the name to ensure that the 3 code paths for the 3 formats work in
the same way.

The tests could be MUCH better. If the spirit moves you to design or
implement a much more intelligent test strategy, please know that your
efforts will be welcome and appreciated.

Unless you add better coverage someplace else, add a few examples of
your names to `TEST_NAMES`. A test attempts to try the 3 different
comma variations of these names automatically and make sure things
don't blow up, so it can be a helpful regression indicator.


New Releases
------------

[https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/](Publishing to Pypi Guide)

    $ python setup.py sdist bdist_wheel
    $ twine upload dist/*

