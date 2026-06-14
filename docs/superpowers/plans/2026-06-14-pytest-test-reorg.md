# Pytest Test Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single 97KB `tests.py` into a `tests/` package (one file per concern) and run it under pytest, preserving every existing test and the dual-run-under-two-configs behavior.

**Architecture:** Each existing `unittest`-style test class moves verbatim into its own `tests/test_*.py` file. The shared base class becomes a *plain* class (not `unittest.TestCase`) carrying the custom `m()` assert plus thin `assert*` shims, so test bodies move unchanged AND pytest's parametrized fixtures apply (they do not apply to `unittest.TestCase` subclasses). A single autouse parametrized fixture in `conftest.py` reproduces the original `__main__` block that ran the whole suite twice — once with `empty_attribute_default = ''` and once with `None`.

**Tech Stack:** Python 3.10+, pytest, uv, ruff (with `ANN` + `UP` rule sets enabled), mypy (checks `nameparser` package only — not tests).

---

## Background & Key Decisions (read before starting)

The source today is a single file `tests.py` (344 test methods across 13 classes that subclass `HumanNameTestBase(unittest.TestCase, Generic[T])`). The `__main__` block runs `unittest.main()` twice; the second run sets `CONSTANTS.empty_attribute_default = None` globally.

**Decisions baked into this plan:**

1. **Base class becomes a plain class.** pytest cannot apply *parametrized* fixtures to `unittest.TestCase` subclasses. Since the dual-run is implemented as a parametrized autouse fixture, the base must be a plain class. The base provides `m()` plus `assertEqual/assertTrue/assertFalse/assertIn` shims so the ~78 `self.assert*` call sites move unchanged.
2. **`assertRaises` is NOT shimmed.** It is used only 4 times, all as `with self.assertRaises(TypeError):` in the Python-API tests, and its context-manager return type is awkward to annotate under the `ANN` ruleset. Those 4 sites are converted directly to `with pytest.raises(TypeError):`.
3. **`@unittest.skipUnless(dill, ...)` → `@pytest.mark.skipif(not dill, ...)`.** Two pickling tests use this; `unittest` skip decorators only work on `TestCase` subclasses.
4. **Dual-run = autouse parametrized fixture** over `['', None]`, restoring the prior value after each test. This doubles the run count (344 → 688), exactly matching today's two-pass behavior, and additionally isolates the global-state mutation that currently leaks between the two passes.
5. **Class names are kept** (e.g. `HumanNamePythonTests`, `TitleTestCase`), so `pytest` is configured with `python_classes = ["*Tests", "*TestCase"]`. The one oddball, `ConstantsCustomization`, is renamed to `ConstantsCustomizationTests` for consistency.
6. **The debug CLI moves to `nameparser/__main__.py`** so `python -m nameparser "Some Name"` replaces the old `python tests.py "Some Name"`. (User decision.)
7. **`tests/` is a real package** (`tests/__init__.py` present) so test modules import the base via `from tests.base import HumanNameTestBase`.
8. **`@unittest.expectedFailure` → `@pytest.mark.xfail`.** This decorator only works on `TestCase` subclasses; the plain-class equivalent is `@pytest.mark.xfail`. It appears on **10 methods** spread across 5 classes (see the "xfail" column in the table). Any file containing one of these needs `import pytest` in its header, and its reported count splits into `passed` + `xfailed` (both are success states — only `failed`/`error` are bad). The 4 `skipUnless` → `skipif` conversions in Task 2 are the analogous case for skips.

**Source-of-truth line ranges in the current `tests.py`** (for the verbatim moves):

| Class | Lines | Methods | Expected pytest count (×2) | Extra imports beyond base + HumanName |
|---|---|---|---|---|
| `HumanNamePythonTests` | 54–266 | 31 | 62 | `re`, `pytest`, `dill` (try/except), `Constants`, `TupleManager` |
| `FirstNameHandlingTests` | 267–330 | 11 | 18 passed, 4 xfailed | `pytest` (2 xfail) |
| `HumanNameBruteForceTests` | 331–1135 | 117 | 234 passed | — |
| `HumanNameConjunctionTestCase` | 1136–1333 | 32 | 60 passed, 4 xfailed | `pytest` (2 xfail) |
| `ConstantsCustomization` → `ConstantsCustomizationTests` | 1334–1435 | 11 | 22 passed | `Constants`, `CONSTANTS` |
| `NicknameTestCase` | 1436–1608 | 18 | 34 passed, 2 xfailed | `pytest` (1 xfail) |
| `PrefixesTestCase` | 1609–1723 | 18 | 36 passed | — |
| `SuffixesTestCase` | 1724–1856 | 21 | 40 passed, 2 xfailed | `pytest` (1 xfail) |
| `TitleTestCase` | 1857–2091 | 37 | 68 passed, 6 xfailed | `pytest` (3 xfail) |
| `HumanNameCapitalizationTestCase` | 2092–2170 | 14 | 26 passed, 2 xfailed | `pytest` (1 xfail) |
| `HumanNameOutputFormatTests` | 2171–2293 | 15 | 30 passed | `Constants`, `CONSTANTS` |
| `InitialsTestCase` | 2294–2401 | 18 | 36 passed | `CONSTANTS` |
| `TEST_NAMES` tuple | 2402–2578 | — | — | (data; lives in `test_variations.py`) |
| `HumanNameVariationTests` | 2581–2608 | 1 | 2 passed | — (uses `TEST_NAMES` from same file) |
| **TOTAL** | | **344** | **668 passed, 20 xfailed** | |

**`@unittest.expectedFailure` handling (applies to the move tasks below):** any class whose row shows an xfail count contains that many `@unittest.expectedFailure` decorators. In the moved file, (a) add `import pytest` to the header, and (b) replace each `@unittest.expectedFailure` line with `@pytest.mark.xfail`. Leave the decorated method body unchanged. These convert `unittest`'s expected-failure marker (which only works on `TestCase`) into pytest's equivalent.

`CONSTANTS` / `Constants` / `TupleManager` are imported from `nameparser.config`. `HumanName` from `nameparser`.

**Note on `m()`:** keep its `try/except UnicodeDecodeError` fallback and its awareness of `hn.C.empty_attribute_default` exactly as in the original.

---

## Task 1: Scaffold the pytest package and prove the harness

This task creates the package, the plain base class, the dual-run fixture, the pytest config, adds the pytest dependency, and moves the **simplest** class (`FirstNameHandlingTests`) to validate the whole harness end-to-end before the mechanical moves.

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/base.py`
- Create: `tests/conftest.py`
- Create: `tests/test_first_name.py`
- Modify: `pyproject.toml` (add `pytest` to dev group; add `[tool.pytest.ini_options]`)

- [ ] **Step 1: Create the package marker**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 2: Create the plain base class**

Create `tests/base.py`:

```python
from typing import Generic, TypeVar

from nameparser import HumanName

T = TypeVar('T')


class HumanNameTestBase(Generic[T]):
    """Shared assert helpers for the parsing tests.

    Formerly subclassed unittest.TestCase. It is now a plain class so pytest can
    apply the parametrized dual-run fixture in conftest.py — parametrized
    fixtures do not apply to unittest.TestCase subclasses. The assert* methods
    are thin shims so existing test bodies move over unchanged.
    """

    def m(self, actual: T, expected: T, hn: HumanName) -> None:
        """assertEqual with a better message and awareness of hn.C.empty_attribute_default"""
        expected_ = expected or hn.C.empty_attribute_default
        try:
            assert actual == expected_, "'%s' != '%s' for '%s'\n%r" % (
                actual,
                expected,
                hn.original,
                hn,
            )
        except UnicodeDecodeError:
            assert actual == expected_

    def assertEqual(self, first: object, second: object, msg: object = None) -> None:
        assert first == second, msg

    def assertTrue(self, expr: object, msg: object = None) -> None:
        assert expr, msg

    def assertFalse(self, expr: object, msg: object = None) -> None:
        assert not expr, msg

    def assertIn(self, member: object, container: object, msg: object = None) -> None:
        assert member in container, msg  # type: ignore[operator]
```

- [ ] **Step 3: Create the dual-run fixture**

Create `tests/conftest.py`:

```python
from collections.abc import Iterator

import pytest

from nameparser.config import CONSTANTS


@pytest.fixture(autouse=True, params=['', None], ids=['default', 'none'])
def empty_attribute_default(request: pytest.FixtureRequest) -> Iterator[str | None]:
    """Run every test under both empty_attribute_default settings.

    Reproduces the original tests.py __main__ block, which ran the whole suite
    twice — once with the default ('') and once with None — as a regression
    check that the three parsing code paths agree. Restoring after each test
    also isolates the global-state mutation that previously leaked between runs.
    """
    original = CONSTANTS.empty_attribute_default
    CONSTANTS.empty_attribute_default = request.param
    yield request.param
    CONSTANTS.empty_attribute_default = original
```

- [ ] **Step 4: Move `FirstNameHandlingTests` into its own file**

Create `tests/test_first_name.py` with this header, then paste the **body** of `FirstNameHandlingTests` (the class line and everything indented under it, lines 267–330 of `tests.py`) verbatim. This class has **two** `@unittest.expectedFailure` decorators (lines 280, 323) — replace each with `@pytest.mark.xfail` (leave the method bodies unchanged):

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 267-330 of tests.py here, starting at:
# class FirstNameHandlingTests(HumanNameTestBase):
# ...and change the two `@unittest.expectedFailure` lines to `@pytest.mark.xfail`
```

- [ ] **Step 5: Add pytest dependency and config to `pyproject.toml`**

In the `[dependency-groups]` `dev` list, add `"pytest (>=8)"`:

```toml
[dependency-groups]
dev = [
  "pytest (>=8)",
  "dill (>=0.2.5)",
  "sphinx (>=8)",
  "mypy (>=2.1)",
  "ruff (>=0.15)"
]
```

Add a new section (place it after `[tool.mypy]`/before or after `[tool.ruff.lint]` — anywhere top-level is fine):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_classes = ["*Tests", "*TestCase"]
```

- [ ] **Step 6: Sync deps and run the new file**

Run: `uv sync`
Then: `uv run pytest tests/test_first_name.py -q`
Expected: `18 passed, 4 xfailed` (9 passing methods × 2, plus 2 xfail methods × 2). Zero failures. Test ids look like `test_first_name[default]` and `test_first_name[none]`.

- [ ] **Step 7: Confirm ruff is clean on the new files**

Run: `uv run ruff check tests/`
Expected: no errors. (If `ANN` complains about the `assertIn` operator on `object`, the `# type: ignore` is for mypy only; ruff should pass. Fix any genuine annotation gaps ruff reports.)

- [ ] **Step 8: Commit**

```bash
git add tests/__init__.py tests/base.py tests/conftest.py tests/test_first_name.py pyproject.toml uv.lock
git commit -m "test: scaffold pytest package with dual-run fixture and first module"
```

---

## Task 2: Move `HumanNamePythonTests` (the conversion-heavy one)

This is the only class needing real edits beyond a move: `re` import, `dill` skip decorators, and `assertRaises` → `pytest.raises`.

**Files:**
- Create: `tests/test_python_api.py`

- [ ] **Step 1: Create the file with the full header**

Create `tests/test_python_api.py`:

```python
import re

import pytest

try:
    import dill
except ImportError:
    dill = False  # type: ignore[assignment]

from nameparser import HumanName
from nameparser.config import Constants, TupleManager

from tests.base import HumanNameTestBase


# <-- paste lines 54-266 of tests.py here, starting at:
# class HumanNamePythonTests(HumanNameTestBase):
```

- [ ] **Step 2: Convert the two pickling skip decorators**

In the pasted body, replace both occurrences of:

```python
    @unittest.skipUnless(dill, "requires python-dill module to test pickling")
```

with:

```python
    @pytest.mark.skipif(not dill, reason="requires python-dill module to test pickling")
```

- [ ] **Step 3: Convert the four `assertRaises` context managers**

In the pasted body, replace all four occurrences of:

```python
        with self.assertRaises(TypeError):
```

with:

```python
        with pytest.raises(TypeError):
```

- [ ] **Step 4: Verify no stray `unittest` references remain**

Run: `grep -n "unittest" tests/test_python_api.py`
Expected: no output. (If anything prints, convert it before proceeding.)

- [ ] **Step 5: Run the file**

Run: `uv run pytest tests/test_python_api.py -q`
Expected: `62 passed` (31 × 2). The two pickling tests are skipped if `dill` is absent — with dill installed (it is in the dev group) they run, so expect `62 passed`. If dill is somehow missing: `58 passed, 4 skipped`.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check tests/test_python_api.py
git add tests/test_python_api.py
git commit -m "test: move HumanNamePythonTests to tests/test_python_api.py"
```

---

## Task 3: Move `HumanNameBruteForceTests`

**Files:**
- Create: `tests/test_brute_force.py`

- [ ] **Step 1: Create the file**

Create `tests/test_brute_force.py`:

```python
from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 331-1135 of tests.py here, starting at:
# class HumanNameBruteForceTests(HumanNameTestBase):
```

- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/test_brute_force.py -q`
Expected: `234 passed` (117 × 2).

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_brute_force.py
git add tests/test_brute_force.py
git commit -m "test: move HumanNameBruteForceTests to tests/test_brute_force.py"
```

---

## Task 4: Move `HumanNameConjunctionTestCase`

**Files:**
- Create: `tests/test_conjunctions.py`

- [ ] **Step 1: Create the file**

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 1136-1333 of tests.py here, starting at:
# class HumanNameConjunctionTestCase(HumanNameTestBase):
# This class has TWO @unittest.expectedFailure decorators (lines 1218, 1322).
# Change each to @pytest.mark.xfail; leave the method bodies unchanged.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_conjunctions.py -q`
Expected: `60 passed, 4 xfailed` (30 passing × 2, 2 xfail × 2). Zero failures.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_conjunctions.py
git add tests/test_conjunctions.py
git commit -m "test: move HumanNameConjunctionTestCase to tests/test_conjunctions.py"
```

---

## Task 5: Move `ConstantsCustomization` (with rename)

**Files:**
- Create: `tests/test_constants.py`

- [ ] **Step 1: Create the file**

```python
from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants

from tests.base import HumanNameTestBase


# <-- paste lines 1334-1435 of tests.py here, starting at:
# class ConstantsCustomization(HumanNameTestBase):
```

- [ ] **Step 2: Rename the class for collection consistency**

Change the pasted class line from:

```python
class ConstantsCustomization(HumanNameTestBase):
```

to:

```python
class ConstantsCustomizationTests(HumanNameTestBase):
```

- [ ] **Step 3: Run**

Run: `uv run pytest tests/test_constants.py -q`
Expected: `22 passed` (11 × 2).

- [ ] **Step 4: Lint and commit**

```bash
uv run ruff check tests/test_constants.py
git add tests/test_constants.py
git commit -m "test: move ConstantsCustomization to tests/test_constants.py and rename for pytest collection"
```

---

## Task 6: Move `NicknameTestCase`

**Files:**
- Create: `tests/test_nicknames.py`

- [ ] **Step 1: Create the file**

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 1436-1608 of tests.py here, starting at:
# class NicknameTestCase(HumanNameTestBase):
# This class has ONE @unittest.expectedFailure decorator (line 1557).
# Change it to @pytest.mark.xfail; leave the method body unchanged.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_nicknames.py -q`
Expected: `34 passed, 2 xfailed` (17 passing × 2, 1 xfail × 2). Zero failures.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_nicknames.py
git add tests/test_nicknames.py
git commit -m "test: move NicknameTestCase to tests/test_nicknames.py"
```

---

## Task 7: Move `PrefixesTestCase`

**Files:**
- Create: `tests/test_prefixes.py`

- [ ] **Step 1: Create the file**

```python
from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 1609-1723 of tests.py here, starting at:
# class PrefixesTestCase(HumanNameTestBase):
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_prefixes.py -q`
Expected: `36 passed` (18 × 2).

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_prefixes.py
git add tests/test_prefixes.py
git commit -m "test: move PrefixesTestCase to tests/test_prefixes.py"
```

---

## Task 8: Move `SuffixesTestCase`

**Files:**
- Create: `tests/test_suffixes.py`

- [ ] **Step 1: Create the file**

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 1724-1856 of tests.py here, starting at:
# class SuffixesTestCase(HumanNameTestBase):
# This class has ONE @unittest.expectedFailure decorator (line 1831).
# Change it to @pytest.mark.xfail; leave the method body unchanged.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_suffixes.py -q`
Expected: `40 passed, 2 xfailed` (20 passing × 2, 1 xfail × 2). Zero failures.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_suffixes.py
git add tests/test_suffixes.py
git commit -m "test: move SuffixesTestCase to tests/test_suffixes.py"
```

---

## Task 9: Move `TitleTestCase`

**Files:**
- Create: `tests/test_titles.py`

- [ ] **Step 1: Create the file**

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 1857-2091 of tests.py here, starting at:
# class TitleTestCase(HumanNameTestBase):
# This class has THREE @unittest.expectedFailure decorators (lines 1903, 1939, 2030).
# Change each to @pytest.mark.xfail; leave the method bodies unchanged.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_titles.py -q`
Expected: `68 passed, 6 xfailed` (34 passing × 2, 3 xfail × 2). Zero failures.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_titles.py
git add tests/test_titles.py
git commit -m "test: move TitleTestCase to tests/test_titles.py"
```

---

## Task 10: Move `HumanNameCapitalizationTestCase`

**Files:**
- Create: `tests/test_capitalization.py`

- [ ] **Step 1: Create the file**

```python
import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 2092-2170 of tests.py here, starting at:
# class HumanNameCapitalizationTestCase(HumanNameTestBase):
# This class has ONE @unittest.expectedFailure decorator (line 2100).
# Change it to @pytest.mark.xfail; leave the method body unchanged.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_capitalization.py -q`
Expected: `26 passed, 2 xfailed` (13 passing × 2, 1 xfail × 2). Zero failures.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_capitalization.py
git add tests/test_capitalization.py
git commit -m "test: move HumanNameCapitalizationTestCase to tests/test_capitalization.py"
```

---

## Task 11: Move `HumanNameOutputFormatTests`

**Files:**
- Create: `tests/test_output_format.py`

- [ ] **Step 1: Create the file**

```python
from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants

from tests.base import HumanNameTestBase


# <-- paste lines 2171-2293 of tests.py here, starting at:
# class HumanNameOutputFormatTests(HumanNameTestBase):
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_output_format.py -q`
Expected: `30 passed` (15 × 2).

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_output_format.py
git add tests/test_output_format.py
git commit -m "test: move HumanNameOutputFormatTests to tests/test_output_format.py"
```

---

## Task 12: Move `InitialsTestCase`

Note: only the class moves here — the `TEST_NAMES` tuple that follows it (lines 2402–2578) belongs to Task 13. Paste **only** lines 2294–2401.

**Files:**
- Create: `tests/test_initials.py`

- [ ] **Step 1: Create the file**

```python
from nameparser import HumanName
from nameparser.config import CONSTANTS

from tests.base import HumanNameTestBase


# <-- paste lines 2294-2401 of tests.py here, starting at:
# class InitialsTestCase(HumanNameTestBase):
# Stop BEFORE the `TEST_NAMES = (` line at 2402.
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_initials.py -q`
Expected: `36 passed` (18 × 2).

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_initials.py
git add tests/test_initials.py
git commit -m "test: move InitialsTestCase to tests/test_initials.py"
```

---

## Task 13: Move `TEST_NAMES` + `HumanNameVariationTests`

The `TEST_NAMES` tuple (lines 2402–2578) and the class that consumes it move together into one file.

**Files:**
- Create: `tests/test_variations.py`

- [ ] **Step 1: Create the file**

Paste the `TEST_NAMES = ( ... )` tuple (lines 2402–2578) first, then the `HumanNameVariationTests` class (lines 2581–2608), under this header:

```python
from nameparser import HumanName

from tests.base import HumanNameTestBase


# <-- paste lines 2402-2578 (the TEST_NAMES tuple) here, then a blank line, then
# paste lines 2581-2608, starting at:
# class HumanNameVariationTests(HumanNameTestBase):
```

The class keeps its `TEST_NAMES = TEST_NAMES` line verbatim (it aliases the module-level tuple onto the class).

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_variations.py -q`
Expected: `2 passed` (1 method × 2).

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff check tests/test_variations.py
git add tests/test_variations.py
git commit -m "test: move TEST_NAMES and HumanNameVariationTests to tests/test_variations.py"
```

---

## Task 14: Move the debug CLI to `nameparser/__main__.py`, delete `tests.py`

**Files:**
- Create: `nameparser/__main__.py`
- Delete: `tests.py`

- [ ] **Step 1: Create `nameparser/__main__.py`**

This replicates the old `python tests.py "name"` debug path as `python -m nameparser "name"`:

```python
"""Command-line debug helper: parse a name and print the result.

Usage:

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
"""
import logging
import sys

from nameparser import HumanName


def main() -> None:
    if len(sys.argv) <= 1:
        print('Usage: python -m nameparser "Name String"')
        raise SystemExit(1)
    log = logging.getLogger('HumanName')
    log.setLevel(logging.ERROR)
    log.addHandler(logging.StreamHandler())
    name_string = sys.argv[1]
    hn = HumanName(name_string, encoding=sys.stdout.encoding)
    print(repr(hn))
    hn.capitalize()
    print(repr(hn))
    print("Initials: " + hn.initials())


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify the CLI works**

Run: `uv run python -m nameparser "Dr. Juan Q. Xavier de la Vega III"`
Expected: a `<HumanName : [ ... ]>` repr printed twice (raw, then capitalized) followed by an `Initials:` line.

- [ ] **Step 3: Delete the old test file**

Run: `git rm tests.py`

- [ ] **Step 4: Run the entire suite**

Run: `uv run pytest -q`
Expected: `668 passed, 20 xfailed` (334 passing methods × 2, plus 10 `xfail` methods × 2 = 688 collected). Zero failures, zero errors. With dill present (dev group), no skips.

- [ ] **Step 5: Run ruff and mypy across the repo**

Run: `uv run ruff check`
Run: `uv run mypy`
Expected: both clean. (mypy is configured to check only `nameparser`, so the new `__main__.py` is type-checked but the tests are not.)

- [ ] **Step 6: Commit**

```bash
git add nameparser/__main__.py
git rm tests.py
git commit -m "feat: add 'python -m nameparser' debug CLI; remove monolithic tests.py"
```

---

## Task 15: Update docs and CI to use pytest

**Files:**
- Modify: `.github/workflows/python-package.yml` (line ~43)
- Modify: `CONTRIBUTING.md` (Running Tests section)
- Modify: `AGENTS.md` (test commands + Tests section)

- [ ] **Step 1: Update CI**

In `.github/workflows/python-package.yml`, under the `Run Tests` step, replace:

```yaml
        python tests.py
```

with:

```yaml
        pytest
```

(The `--group dev` install already brings in pytest.)

- [ ] **Step 2: Update `CONTRIBUTING.md`**

Replace the `Running Tests` block:

```
Running Tests
---------------

    python tests.py

You can also pass a name string to `tests.py` to see how it will be parsed:

    $ python tests.py "Secretary of State Hillary Rodham-Clinton"
```

with:

```
Running Tests
---------------

    pytest

Run a single test file or test:

    pytest tests/test_titles.py
    pytest tests/test_titles.py -k test_two_part_title

You can also pass a name string to see how it will be parsed:

    $ python -m nameparser "Secretary of State Hillary Rodham-Clinton"
```

Leave the surrounding example output and the `Writing Tests` paragraph about `TEST_NAMES` intact (the `TEST_NAMES` tuple still exists, now in `tests/test_variations.py`).

- [ ] **Step 3: Update `AGENTS.md`**

Replace the test-command block:

```
# Run all tests
python tests.py

# Run a single test by class/method
python -m unittest tests.HumanNamePythonTests.test_utf8

# ...
python tests.py "Dr. Juan Q. Xavier de la Vega III"
```

with:

```
# Run all tests
pytest

# Run a single test file / class / method
pytest tests/test_python_api.py
pytest tests/test_python_api.py::HumanNamePythonTests::test_utf8

# Parse a name string to see how it parses
python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
```

Then update the `### Tests (tests.py)` section: rename it to `### Tests (tests/)` and rewrite its body to describe the new layout — one file per concern under `tests/`, the plain `HumanNameTestBase.m()` helper in `tests/base.py`, the autouse `empty_attribute_default` fixture in `tests/conftest.py` that runs every test under both `''` and `None` (so reported counts are doubled), and that `TEST_NAMES` now lives in `tests/test_variations.py`.

- [ ] **Step 4: Sanity-check the doc commands**

Run: `uv run pytest tests/test_python_api.py::HumanNamePythonTests::test_utf8 -q`
Expected: `2 passed` (the dual-run params).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/python-package.yml CONTRIBUTING.md AGENTS.md
git commit -m "docs: update test instructions and CI for pytest"
```

---

## Final verification (after all tasks)

- [ ] `uv run pytest -q` → `668 passed, 20 xfailed` (688 collected, zero failures)
- [ ] `uv run ruff check` → clean
- [ ] `uv run mypy` → clean
- [ ] `uv run python -m nameparser "Dr. Juan Q. Xavier de la Vega III"` → prints parsed repr
- [ ] `git status` shows `tests.py` deleted and `tests/` + `nameparser/__main__.py` added
- [ ] No file in `tests/` contains the string `unittest`: `grep -rn unittest tests/` → no output
```
