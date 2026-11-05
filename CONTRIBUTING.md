Contributing
==============

Ask before you open a pull request
------------------------------------

Bug reports, questions and proposals are welcome as issues. Pull requests are
not, unless one was agreed first. Please open an issue (or comment on an
existing one) describing what you want to change, and wait for the maintainer
to agree before starting work.

Open issues are not a list of tasks waiting for a volunteer. Every issue is
assigned to the maintainer, and most are already being worked on. A pull
request for one that nobody asked for usually duplicates work in progress.

Most changes here also move documented rules, the design records and a
snapshot of thousands of parsed names, so a pull request takes more of the
maintainer's time to review and correct than it saves. That is why the
discussion comes first. Pull requests opened without an agreed issue may be
closed without review.

Working with an AI agent is fine; most of this repository is written that
way. Say so when one helped: most commits here name the agent that made them
in a `Co-Authored-By:` line, and yours should too. What matters is that
someone is steering.

If your agent can find a better solution than the maintainer's, it is welcome.
Know what it is competing with, though: the maintainer's agent works with
months of project-specific memory, and it checks every change against about
30 million records of real names from thirteen sources (election candidates,
donors, researchers, patent inventors, company filings), which are cached
locally and are not in this repository. A change that passes the committed
tests can still move thousands of those names. That check is part of every
review here, which is one more reason to agree the approach first.

Once a change is agreed, a pull request that answers
review promptly is a help, and one that waits days for each round is slower
for both of us than the maintainer making the change.

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
