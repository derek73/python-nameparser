# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dev dependencies (requires pip >= 24.1)
pip install --group dev

# Run all tests
python tests.py

# Run a single test by class/method
python -m unittest tests.HumanNamePythonTests.test_utf8

# Debug how a specific name string is parsed (prints HumanName repr)
python tests.py "Dr. Juan Q. Xavier de la Vega III"

# Build docs
sphinx-build -b html docs dist/docs

# Build package for release
python setup.py sdist bdist_wheel
twine upload dist/*
```

Enable debug logging to see the parser's internal decisions:

```python
import logging
logging.getLogger('HumanName').setLevel(logging.DEBUG)
```

## Architecture

The library has two layers: `nameparser/config/` (data) and `nameparser/parser.py` (logic).

### Configuration layer (`nameparser/config/`)

Each module defines a plain Python set of known name pieces:

- `titles.py` — `TITLES` (prenominals) and `FIRST_NAME_TITLES` (e.g. "Sir", which treat the following name as first, not last)
- `suffixes.py` — `SUFFIX_ACRONYMS` (with periods, e.g. "M.D.") and `SUFFIX_NOT_ACRONYMS` (e.g. "Jr.")
- `prefixes.py` — `PREFIXES` (lastname particles, e.g. "de", "van")
- `conjunctions.py` — `CONJUNCTIONS` (e.g. "and", "of") used to chain multi-word titles
- `capitalization.py` — `CAPITALIZATION_EXCEPTIONS` mapping (e.g. `{'phd': 'Ph.D.'}`)
- `regexes.py` — compiled regular expressions wrapped in a `TupleManager`

`config/__init__.py` wraps everything into `SetManager` and `TupleManager` instances inside a `Constants` class. A module-level singleton `CONSTANTS` is shared across all `HumanName` instances by default.

**Two-tier config pattern**: `CONSTANTS` is global; passing `None` as the second arg to `HumanName` creates a fresh per-instance `Constants()`. After modifying per-instance config you must call `hn.parse_full_name()` again. `SetManager.add()`/`remove()` normalizes inputs to lowercase with no periods, so callers don't need to worry about case.

### Parser (`nameparser/parser.py`)

`HumanName` is the single public class. Assigning to `full_name` (or instantiating with a string) triggers `parse_full_name()`.

Parse flow:
1. `pre_process()` — strips nicknames (parenthesis/quotes) and emoji, fixes "Ph.D." variant spellings
2. Split on commas → 1 part (no comma), 2 parts (suffix-comma or lastname-comma), 3+ parts
3. `parse_pieces()` — splits on spaces, detects dotted abbreviations like "Lt.Gov." and adds them to constants dynamically
4. `join_on_conjunctions()` — merges pieces adjacent to conjunctions into single tokens (e.g. `['Secretary', 'of', 'State']` → `['Secretary of State']`); also joins prefix particles to the following lastname token
5. Iterates pieces, assigning to `title_list`, `first_list`, `middle_list`, `last_list`, `suffix_list`
6. `post_process()` — `handle_firstnames()` swaps first/last when only a title + one name; `handle_capitalization()` applies optional auto-cap

Each named attribute (`title`, `first`, etc.) is a `@property` that joins its corresponding `_list`. Setters call `_set_list()` which runs the value through `parse_pieces()`, so assigning `hn.last = "de la Vega"` correctly re-parses prefix tokens.

### Tests (`tests.py`)

All tests live in a single file. `HumanNameTestBase.m()` is a custom assert helper that prints the original name string on failure. Many test classes group cases by name format type. `TEST_NAMES` is a list of name strings that gets automatically permuted into comma-separated variants as a regression check. When adding a new parsing case, add it to the relevant test class and consider adding the base form to `TEST_NAMES`.
