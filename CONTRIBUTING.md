Contributing
==============

Issues, not pull requests
---------------------------

Bug reports, questions and proposals are welcome as issues. Pull requests are
open to collaborators only.

The most useful thing you can bring is what the code cannot know: the name
that reads wrong, how it should read, and the convention behind it (who
writes names that way, and where). Tell us what you use the parser for, too:
what your names look like, where they come from, and what you need from the
result. The maintainer can only guess how people use it, and knowing why you
want a reading often changes how it is built. Put that in an issue. A few
real examples are worth more than a fix.

Open issues are not a list of tasks waiting for a volunteer. Every issue is
assigned to the maintainer, and most are already being worked on.

Why the maintainer makes the changes
--------------------------------------

Most changes here also move documented rules, the design records and a
snapshot of thousands of parsed names. The maintainer checks every change
against about 30 million records of real names from thirteen sources
(election candidates, donors, researchers, patent inventors, company filings).
The tools that fetch them are in this repository, but the names are not: the
cache is about 12 GB, and one source alone takes about twelve hours to
download. A change that passes the committed tests can still move thousands
of those names, for better or worse, and the committed snapshot sees none of
them. So a change made outside that setup needs several rounds of review
before it is done, and that costs both of us more than the maintainer making
it.

You are welcome to review the pull request that fixes your issue. Comments on
it are open to everyone, and that is where your knowledge of the names counts
most.

If you already have a fix
---------------------------

Push it to a branch on your fork and link the branch in the issue. The
maintainer may build on it, or take a different route once the corpora show
what it moves. Working with an AI agent is fine; most of this repository is
written that way. Every commit an agent helped write names it in a
`Co-Authored-By:` line, here and in yours, so that a commit without one can
be read as written by a person alone. If your commits do, you will be
credited the same way on the commit that lands your work.

Development Environment Setup
--------------------------------

Install dev dependencies:

    uv sync

Running Tests
---------------

    uv run pytest  # parallel; --doctest-modules is set in pyproject.toml, so doctests run too
    uv run pytest -n0 -m serial  # the clock-timed benchmarks, which a parallel run skips

`-n0` runs the whole suite serially in one process.

Run a single test file or test:

    uv run pytest tests/test_titles.py
    uv run pytest tests/test_titles.py::TitleTestCase

You can also pass a name string to see how it will be parsed:

    $ python -m nameparser "secretary of state hillary rodham-clinton"
    Parsed:
    <ParsedName: [
        title: 'secretary of state'
        given: 'hillary'
        family: 'rodham-clinton'
    ]>
    Capitalized:
    <ParsedName: [
        title: 'Secretary of State'
        given: 'Hillary'
        family: 'Rodham-Clinton'
    ]>
    Initials: h. r.

CI runs tests against every supported Python version (see the matrix in `.github/workflows/python-package.yml`) via GitHub Actions on every push and pull request.

Changing the Word Lists
-------------------------

The default vocabulary (titles, suffixes, particles and the rest) lives in
`nameparser/vocab/*.toml`, one file per language tag and one entry per word,
listing what the word can be read as. The parser reads a module compiled from
those files, so after editing one, rebuild it:

    uv run python tools/vocab/build.py

The build checks the files and refuses, with a message, a mistake it can
detect: a typo in a kind or property, an unnormalized spelling, a reading a
word is recorded as refused. `tools/vocab/query.py` looks words up
(`--word`, `--kind`, `--issue`, `--excluded`).

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
