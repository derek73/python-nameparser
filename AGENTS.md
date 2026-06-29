# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow

For non-trivial changes, use a feature branch and open a PR.
Branch naming: `fix/issue-NNN-short-description` or `feat/short-description`.

## Commands

```bash
# Preferred: use uv run (works without activating the venv)
# Alternative: .venv/bin/<tool> if the venv is already active

# Run all tests (includes --doctest-modules, so doctests in nameparser/ are also run;
# the dual-parametrize fixture doubles the count, so ~370 methods → ~740 results)
uv run pytest

# Run a single test file / class / method
uv run pytest tests/test_python_api.py
uv run pytest tests/test_python_api.py::HumanNamePythonTests::test_utf8

# Type check
uv run mypy nameparser/

# Lint
uv run ruff check nameparser/

# Debug how a specific name string is parsed (prints HumanName repr)
python -m nameparser "Dr. Juan Q. Xavier de la Vega III"

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

**`_CachedUnionMember` descriptor**: The four PST-contributing attrs (`prefixes`, `suffix_acronyms`, `suffix_not_acronyms`, `titles`) are managed by this descriptor, which stores their values under the *private* name (`_prefixes`, `_titles`, etc.) in the instance `__dict__` so that the descriptor's `__set__` owns every assignment and can wire the cache-invalidation callback. Any code that inspects `__dict__` directly (e.g. `__getstate__`) must map `_xxx` → `xxx` for descriptor-managed attrs rather than filtering on `not k.startswith('_')`.

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

## Extension Patterns

**Adding a scalar `Constants` attribute + `HumanName` kwarg** (e.g. `initials_separator`, `suffix_delimiter`):
1. Add class attr to `Constants` in `config/__init__.py` with docstring
2. Add `x: str | None = None` to `HumanName.__init__` signature after related kwargs
3. Add `self.x = x if x is not None else self.C.x` in body — use `is not None`, not `or`, to allow falsy values like `""`
4. conftest auto-restores scalar CONSTANTS between tests, but tests that *set* CONSTANTS mid-run still need their own try/finally

### Tests (`tests/`)

Tests run under **pytest** (via `.venv/bin/pytest`) and are split one file per concern (`tests/test_titles.py`, `tests/test_suffixes.py`, etc.). `tests/base.py` holds `HumanNameTestBase` — a plain (non-`unittest`) base whose `m()` helper is a custom assert that prints the original name string on failure (plus thin `assert*` shims so the moved test bodies are unchanged). `tests/conftest.py` defines an autouse fixture that runs **every test twice** — once with `empty_attribute_default = ''` and once with `None` — so reported counts are doubled (e.g. 11 methods → 22 results); it also snapshots/restores the scalar `CONSTANTS` config around each test to keep tests order-independent. `TEST_NAMES` (in `tests/test_variations.py`) is a list of name strings permuted into comma-separated variants as a regression check. Tests that should fail use `@pytest.mark.xfail`. When adding a parsing case, add it to the relevant `tests/test_*.py` file and consider adding the base form to `TEST_NAMES`.
