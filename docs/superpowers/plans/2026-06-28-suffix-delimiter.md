# suffix_delimiter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-configurable `suffix_delimiter` that allows suffixes separated by arbitrary strings (e.g. ` - `) to be parsed correctly.

**Architecture:** After splitting the full name on commas, re-split `parts[1:]` on `suffix_delimiter` and flatten. This leaves the name portion (`parts[0]`) untouched and feeds the existing downstream suffix logic exactly the shape of input it already handles. `suffix_delimiter` is exposed as a class attribute on `Constants` (global default) and as a `HumanName.__init__` kwarg (per-instance override), mirroring the `initials_separator` pattern.

**Tech Stack:** Python 3, pytest, nameparser internal APIs only.

---

### Task 1: Add `suffix_delimiter` to `Constants`

**Files:**
- Modify: `nameparser/config/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_suffixes.py` inside `SuffixesTestCase`:

```python
def test_suffix_delimiter_default_on_constants(self) -> None:
    from nameparser.config import CONSTANTS
    self.assertIsNone(CONSTANTS.suffix_delimiter)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_default_on_constants -v
```

Expected: `FAIL` — `AttributeError: type object 'Constants' has no attribute 'suffix_delimiter'`

- [ ] **Step 3: Add the attribute to `Constants`**

In `nameparser/config/__init__.py`, locate the block of scalar class attributes (near line 202 where `string_format`, `initials_delimiter`, `initials_separator` are defined). Add after `initials_separator`:

```python
suffix_delimiter = None
"""
If set, an additional delimiter used to split suffix groups after
comma-splitting. For example, setting ``suffix_delimiter=" - "`` allows
``"RN - CRNA"`` to be parsed as two separate suffixes. Default is
``None`` (no additional splitting beyond the standard comma split).

Note: setting this to ``", "`` is a no-op — comma-splitting already
occurs unconditionally before this step.
"""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_default_on_constants -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add nameparser/config/__init__.py tests/test_suffixes.py
git commit -m "feat: add suffix_delimiter to Constants (default None)"
```

---

### Task 2: Wire `suffix_delimiter` into `HumanName`

**Files:**
- Modify: `nameparser/parser.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_suffixes.py` inside `SuffixesTestCase`:

```python
def test_suffix_delimiter_kwarg_accepted(self) -> None:
    hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
    self.assertEqual(hn.suffix_delimiter, " - ")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_kwarg_accepted -v
```

Expected: `FAIL` — `TypeError: __init__() got an unexpected keyword argument 'suffix_delimiter'`

- [ ] **Step 3: Add kwarg to `HumanName.__init__`**

In `nameparser/parser.py`, add `suffix_delimiter` to the class docstring param list (near line 55):

```python
:param str suffix_delimiter: additional delimiter to split suffix groups
    after comma-splitting, e.g. ``" - "`` for ``"RN - CRNA"``
```

Add to the `__init__` signature (after `initials_separator`, around line 97):

```python
suffix_delimiter: str | None = None,
```

Add to the `__init__` body (after the `initials_separator` assignment, around line 113):

```python
self.suffix_delimiter = suffix_delimiter if suffix_delimiter is not None else self.C.suffix_delimiter
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_kwarg_accepted -v
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add nameparser/parser.py tests/test_suffixes.py
git commit -m "feat: wire suffix_delimiter kwarg into HumanName.__init__"
```

---

### Task 3: Implement post-comma expansion in `parse()`

**Files:**
- Modify: `nameparser/parser.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_suffixes.py` inside `SuffixesTestCase`:

```python
def test_suffix_delimiter_basic(self) -> None:
    hn = HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")
    self.m(hn.first, "Steven", hn)
    self.m(hn.last, "Hardman", hn)
    self.m(hn.suffix, "RN, CRNA", hn)

def test_suffix_delimiter_multiple(self) -> None:
    hn = HumanName("John Doe, MD - PhD - FACS", suffix_delimiter=" - ")
    self.m(hn.first, "John", hn)
    self.m(hn.last, "Doe", hn)
    self.m(hn.suffix, "MD, PhD, FACS", hn)

def test_suffix_delimiter_no_effect_without_comma(self) -> None:
    # suffix_delimiter only applies after the comma split; space-separated
    # suffixes already work via the no-comma parse path
    hn = HumanName("John Doe MD PhD", suffix_delimiter=" - ")
    self.m(hn.first, "John", hn)
    self.m(hn.last, "Doe", hn)
    self.m(hn.suffix, "MD, PhD", hn)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_basic tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_multiple tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_no_effect_without_comma -v
```

Expected: first two `FAIL` (suffix parses incorrectly without expansion), third `PASS` (no-comma path already works).

- [ ] **Step 3: Add expansion step in `parse()`**

In `nameparser/parser.py`, locate `parse()`. Find the line:

```python
parts = [x.strip() for x in self._full_name.split(",")]
```

Insert immediately after it:

```python
if self.suffix_delimiter and len(parts) > 1:
    expanded = [parts[0]]
    for part in parts[1:]:
        expanded.extend([p.strip() for p in part.split(self.suffix_delimiter)])
    parts = expanded
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_basic tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_multiple tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_no_effect_without_comma -v
```

Expected: all three `PASS`

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest --tb=short
```

Expected: all existing tests `PASS`

- [ ] **Step 6: Commit**

```bash
git add nameparser/parser.py tests/test_suffixes.py
git commit -m "feat: expand parts on suffix_delimiter after comma split in parse()"
```

---

### Task 4: Test `CONSTANTS`-level setting and document known limitation

**Files:**
- Modify: `tests/test_suffixes.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_suffixes.py` inside `SuffixesTestCase`:

```python
def test_suffix_delimiter_constants_level(self) -> None:
    from nameparser.config import CONSTANTS
    _orig = CONSTANTS.suffix_delimiter
    try:
        CONSTANTS.suffix_delimiter = " - "
        hn = HumanName("Steven Hardman, RN - CRNA")
        self.m(hn.first, "Steven", hn)
        self.m(hn.last, "Hardman", hn)
        self.m(hn.suffix, "RN, CRNA", hn)
    finally:
        CONSTANTS.suffix_delimiter = _orig

def test_suffix_delimiter_none_by_default_known_limitation(self) -> None:
    # Without suffix_delimiter set, " - " between suffixes breaks parsing.
    # This test documents the known limitation — do not "fix" it.
    hn = HumanName("Steven Hardman, RN - CRNA")
    self.assertNotEqual(hn.first, "Steven")
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_constants_level tests/test_suffixes.py::SuffixesTestCase::test_suffix_delimiter_none_by_default_known_limitation -v
```

Expected: both `PASS`

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest --tb=short
```

Expected: all tests `PASS`

- [ ] **Step 4: Commit**

```bash
git add tests/test_suffixes.py
git commit -m "test: add CONSTANTS-level and known-limitation tests for suffix_delimiter"
```
