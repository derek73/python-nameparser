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

Proposing a pack or another large change
------------------------------------------

For anything significant, open an issue first, so it can be discussed there before anyone builds it. A locale pack is the clearest case; a batch of vocabulary, a new rule and a change to how a kind of name reads are others.

A pack or a vocabulary change is measured against the large local corpora described above, which a contributor is unlikely to have downloaded. So it is usually quicker, and gives a better result, for the maintainers to build it and for the person who proposed it to review it.

What helps most is the report itself:

- the names, as they are written where you met them;
- the reading you expect of each;
- the convention behind it: who writes names that way, and where;
- where that convention is documented, if it is (a style guide, a government form, a standard, a reference work).

None of this is a bar to reporting. A single name that reads wrong is a welcome issue.

If you already have a fix
---------------------------

Push it to a branch on your fork and link the branch in the issue. The
maintainer may build on it, or take a different route once the corpora show
what it moves.

Working with an AI agent
--------------------------

Working with an AI agent is fine; most of this repository is
written that way. Every commit an agent helped write names it in a
`Co-Authored-By:` line, here and in yours, so that a commit without one can
be read as written by a person alone. If your commits do, you will be
credited the same way on the commit that lands your work.

An agent working here reads `AGENTS.md` at the root of the repository first. It holds the same rule on pull requests, and the conventions the code, tests and docs are written to.

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

Type check and lint, as CI does:

    uv run mypy
    uv run ruff check

You can also pass a name string to see how it will be parsed:

    $ uv run python -m nameparser "secretary of state hillary rodham-clinton"
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

[`nameparser/vocab/README.md`](nameparser/vocab/README.md) is the reference for these files: what a file means, how an entry is built, the kinds and properties, and the steps for adding a word.

A word that is right in one language and wrong as a default for everyone may belong in a locale pack instead: it is written in its language's file with `default = false`, and read only by a caller who chooses that language. Say which you expect in the issue, per "Proposing a pack or another large change" above.

Writing Tests
----------------

If you make changes on your fork branch, please include tests with example names that should parse correctly.

Prefer a row in `tests/v2/cases.py`, the table of names and their expected readings. A test in a `tests/test_*.py` file is fine where the table cannot express the case.

A name can reach the parser in four comma shapes, each a different code path, so try yours in each:

- no comma (`John Smith Jr.`);
- a full name before the comma (`John Smith, Jr.`);
- a one-word name before the comma (`Smith, John`);
- nothing before the comma (`, John`, as a CSV file with an empty surname field writes it).

The last two are the ones most often missed. Then try each under the three name orders (`uv run python -m nameparser --help` lists `--order`).

You may also add the base form of your names to `TEST_NAMES` in `tests/test_variations.py`. A test rewrites each of those names with its commas moved and checks that the readings agree, so it can be a helpful regression indicator.

Building the Docs
-------------------

The user documentation is the Sphinx pages in `docs/*.rst`, and their examples are doctests. Build both and read the output, not only the exit code:

    uv run sphinx-build -q -b doctest docs /tmp/doctest
    uv run sphinx-build -q -b html docs /tmp/html

Both should print nothing. The HTML build prints an unresolved link as a warning and still exits 0.

Releases
----------

Releases are cut by the maintainer; the checklist is in `AGENTS.md`, under Commands.
