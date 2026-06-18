Contributing
==============

Development Environment Setup
--------------------------------

Install dev dependencies:

    uv sync

Running Tests
---------------

    pytest

Run a single test file or test:

    pytest tests/test_titles.py
    pytest tests/test_titles.py::TitleTestCase

You can also pass a name string to see how it will be parsed:

    $ python -m nameparser "Secretary of State Hillary Rodham-Clinton"
    <HumanName : [
    	title: 'Secretary of State'
    	first: 'Hillary'
    	middle: ''
    	last: 'Rodham-Clinton'
    	suffix: ''
    	nickname: ''
    ]>

CI runs tests against Python 3.10–3.14 via GitHub Actions on every push and pull request.

Writing Tests
----------------

If you make changes, please include tests with example names that should parse correctly.

It's a good idea to include tests of alternate comma placement formats of the name to ensure that the 3 code paths for the 3 formats work in the same way.

Unless you add better coverage someplace else, add a few examples of your names to `TEST_NAMES`. A test attempts to try the 3 different comma variations of these names automatically and make sure things don't blow up, so it can be a helpful regression indicator.

New Releases
------------

Releases are published automatically to PyPI via GitHub Actions. To cut a release,
create and publish a new GitHub Release — the workflow will build and upload the
package using trusted publishing (no API token or twine needed).
