# suffix_delimiter — Design Spec

**Issue:** #156
**Branch:** fix/issue-156-suffix-delimiter
**Date:** 2026-06-28

## Problem

Names like `"Steven Hardman, RN - CRNA"` parse incorrectly because ` - ` is not
a recognized suffix separator. The parser splits on commas first, leaving
`"RN - CRNA"` as a single part. Splitting that on spaces yields
`["RN", "-", "CRNA"]`, and `"-"` is not a suffix, so `are_suffixes()` returns
False and the parser falls through to a wrong code path.

Both `RN` and `CRNA` are in `SUFFIX_ACRONYMS` — the issue is solely the
delimiter between them.

## Approach

Post-comma-split expansion. After splitting the full name on commas, re-split
`parts[1:]` on `suffix_delimiter` and flatten. This scopes the feature to the
region where suffixes live, leaving `parts[0]` (the name portion) untouched.

## Changes

### `nameparser/config/__init__.py`

Add class-level attribute to `Constants`:

```python
suffix_delimiter = None
"""
If set, an additional delimiter used to split suffix groups after
comma-splitting. For example, setting suffix_delimiter=" - " allows
"RN - CRNA" to be parsed as two separate suffixes. Default is None
(no additional splitting beyond the standard comma split).

Note: setting this to ", " is a no-op — comma-splitting already occurs
unconditionally before this step.
"""
```

### `nameparser/parser.py`

**Constructor signature:**
```python
suffix_delimiter: str | None = None,
```

**Constructor body** (mirrors `initials_separator` pattern):
```python
self.suffix_delimiter = suffix_delimiter if suffix_delimiter is not None else self.C.suffix_delimiter
```

**Docstring entry:**
```
:param str suffix_delimiter: additional delimiter to split suffix groups
    after comma-splitting, e.g. " - " for "RN - CRNA"
```

**`parse()` method** — insert immediately after the comma split:
```python
parts = [x.strip() for x in self._full_name.split(",")]

if self.suffix_delimiter and len(parts) > 1:
    expanded = [parts[0]]
    for part in parts[1:]:
        expanded.extend([p.strip() for p in part.split(self.suffix_delimiter)])
    parts = expanded
```

### `tests/test_suffixes.py`

1. `HumanName("Steven Hardman, RN - CRNA", suffix_delimiter=" - ")` →
   `first="Steven"`, `last="Hardman"`, `suffix="RN, CRNA"`
2. `HumanName("John Doe, MD - PhD - FACS", suffix_delimiter=" - ")` →
   `suffix="MD, PhD, FACS"`
3. `CONSTANTS.suffix_delimiter = " - "` applies to new instances without
   passing the kwarg explicitly
4. `HumanName("Steven Hardman, RN - CRNA")` without `suffix_delimiter` —
   documents existing (broken) behavior as a known limitation, not a regression

## Non-goals

- No change to `are_suffixes()`, `is_suffix()`, or the downstream parse paths —
  expanding `parts` before those checks is sufficient.
- No handling of ` - ` in name portions (e.g. hyphenated last names) — the
  expansion only touches `parts[1:]`.
