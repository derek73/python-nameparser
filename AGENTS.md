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
uv run pytest  # --doctest-modules is set in pyproject.toml, so doctests run automatically

# Run a single test file / class / method
uv run pytest tests/test_python_api.py
uv run pytest tests/test_python_api.py::HumanNamePythonTests::test_utf8

# Type check
uv run mypy nameparser/

# Lint
uv run ruff check nameparser/

# Debug how a specific name string is parsed (prints HumanName repr)
uv run python -m nameparser "Dr. Juan Q. Xavier de la Vega III"

# Build docs
uv run sphinx-build -b html docs dist/docs

# Maintain docs/release_log.rst as changes land:
# - Keep an "Unreleased" entry at the top: `* X.Y.Z - Unreleased`
# - Add one bullet per notable change; prefix with Add/Fix/Remove/Change
# - Reference the issue or PR in parentheses: (#123) or (#123, #124)
#   Use "closes #N" when the change directly resolves the issue
# - Version is decided at release time (patch/minor/major per semver)
# - Format matches existing entries — see 1.3.0 block for a current example

# Release checklist (PyPI publish is triggered automatically by GitHub Actions on release creation)
# 0. Review docs/ for anything stale — especially usage.rst (examples, API surface)
#    and any .rst files that reference config constants or HumanName kwargs
#    Also review AGENTS.md for stale commands, architecture notes, or gotchas
# 1. Bump VERSION in nameparser/_version.py (and the `version:` field in CITATION.cff to match)
# 2. Stamp "Unreleased" → "X.Y.Z - Month DD, YYYY" in docs/release_log.rst
# 3. git commit + git tag -a vX.Y.Z -m "Release X.Y.Z"
# 4. git push origin master && git push origin vX.Y.Z  ← tag must be pushed separately before gh release create
# 5. gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
# 6. Close the vX.Y.Z milestone and create a new "Next Release" one:
#    MILESTONE=$(gh api repos/derek73/python-nameparser/milestones --jq '.[] | select(.title=="vX.Y.Z") | .number')
#    gh api -X PATCH repos/derek73/python-nameparser/milestones/$MILESTONE -f state=closed
#    gh api -X POST repos/derek73/python-nameparser/milestones -f title="Next Release"
```

Enable debug logging to see the parser's internal decisions:

```python
import logging
logging.getLogger('HumanName').setLevel(logging.DEBUG)
```

## Architecture

The library has two layers: `nameparser/config/` (data) and `nameparser/parser.py` (logic).

**Design philosophy — positional and language-agnostic.** The parser assigns parts by *position* plus small sets of words that join to neighbors; it never detects language. A name's language can't be reliably inferred from Latin-script transliteration ("Ali" is Arabic or Italian; "Van"/"Della"/"Bin" are first names in some cultures, particles in others), so language-specific rules belong in opt-in `Constants` config, never global defaults. Many "wrong for language X" reports (#133, #150, #130, #85, #103, #146, #83) are irreducible ambiguities — e.g. `de Mesnil` (want last name) vs `Van Johnson` (want first name) are the same `[prefix][word]` shape. Before adding a rule, confirm it doesn't break the opposite case (run the full suite — Portuguese and "Van Johnson" tests are the usual canaries).

### Configuration layer (`nameparser/config/`)

Each module defines a plain Python set of known name pieces:

- `titles.py` — `TITLES` (prenominals) and `FIRST_NAME_TITLES` (e.g. "Sir", which treat the following name as first, not last)
- `suffixes.py` — `SUFFIX_ACRONYMS` (with periods, e.g. "M.D.") and `SUFFIX_NOT_ACRONYMS` (e.g. "Jr.")
- `prefixes.py` — `PREFIXES` (lastname particles, e.g. "de", "van")
- `first_name_prefixes.py` — `FIRST_NAME_PREFIXES` (bound given-name prefixes, e.g. "abdul", "abu"); `_join_first_name_prefix` joins the first non-title piece to its following piece before the main assignment loop
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
   — a piece merged with a title *or prefix* neighbor is re-registered into that constant set so later steps still recognize it, e.g. `von`+`und`+`zu` → registered as a prefix so the whole phrase joins to the last name (German "von und zu"; PR #191)
4a. `_join_first_name_prefix()` — called immediately after step 4 in both the no-comma and lastname-comma paths; merges bound given-name prefixes (e.g. "abdul") with the next piece before the assignment loop runs; suffixes are still in `pieces` at this point, so the `reserve_last` guard must count non-suffix pieces only
5. Iterates pieces, assigning to `title_list`, `first_list`, `middle_list`, `last_list`, `suffix_list`
6. `post_process()` — `handle_firstnames()` swaps first/last when only a title + one name; then, gated on `patronymic_name_order`, `handle_east_slavic_patronymic_name_order()` and `handle_turkic_patronymic_name_order()` reorder Russian-formal-order and reversed Turkic patronymics; then, gated on `middle_name_as_last`, `handle_middle_name_as_last()` folds `middle_list` into `last_list`; finally `handle_capitalization()` applies optional auto-cap. Any new `self._attr` used by `post_process()` helpers must be initialized in `__init__` (with its default value) — the direct-kwargs path bypasses `parse_full_name()`, so the attribute won't exist otherwise.

Each named attribute (`title`, `first`, etc.) is a `@property` that joins its corresponding `_list`. Setters call `_set_list()` which runs the value through `parse_pieces()`, so assigning `hn.last = "de la Vega"` correctly re-parses prefix tokens.

## Extension Patterns

**Adding a scalar `Constants` attribute + `HumanName` kwarg** (e.g. `initials_separator`, `suffix_delimiter`):
1. Add class attr to `Constants` in `config/__init__.py` with docstring
2. Add `x: str | None = None` to `HumanName.__init__` signature after related kwargs
3. Add `self.x = x if x is not None else self.C.x` in body — use `is not None`, not `or`, to allow falsy values like `""`
4. conftest auto-restores scalar CONSTANTS between tests, but tests that *set* CONSTANTS mid-run still need their own try/finally
5. Update `docs/customize.rst`'s constants list (and `docs/usage.rst` if it affects a documented example) — don't wait for the release checklist, these `.rst` docs aren't covered by CI so a stale one can ship silently.

**Adding a new mutable/collection `Constants` attribute** (a `SetManager`/`TupleManager`-backed group, e.g. `extra_nickname_delimiters`): add it to `_COLLECTION_CONFIG_ATTRS` in `tests/conftest.py`, or tests that mutate the global `CONSTANTS` copy will leak state into later tests. Contents must be deep-copyable (the snapshot uses `copy.deepcopy`) — already true for the existing manager types.

Add a dedicated `copy.deepcopy()` round-trip test for it too (see `test_regexes_deepcopy_roundtrip`/`test_extra_nickname_delimiters_deepcopy_roundtrip` in `tests/test_constants.py`), not just reliance on conftest's autouse snapshot/restore exercising it incidentally. `TupleManager`/`RegexTupleManager.__getattr__` answer *any* unknown attribute lookup — including dunder probes like `__deepcopy__` — so a new manager subtype or a `__getattr__` tweak can silently break `copy.deepcopy` (this bit `RegexTupleManager` before the dunder-lookup guard was added). A direct test on the new attribute's own manager instance catches that where the conftest fixture, which never asserts on the copy, would not.

**Adding a word to a config set** — first check the *other* sets for the same word (grep `nameparser/config/` or intersect the sets in a `python3 -c`). Real overlaps exist: `do`/`st`/`mc` ∈ `PREFIXES` ∩ `TITLES`/`SUFFIX_ACRONYMS`; `abd` = "ABD" ∈ `SUFFIX_ACRONYMS`; `abu` ∈ `PREFIXES` ∩ `first_name_prefixes` (position-dependent: leading token → first-name join, mid-name → last-name join). Usually position-dependent and harmless, but can force a guard or an exclusion (the `last_base` all-particles guard; dropping `abd` from `first_name_prefixes`).

**Before adding a short/common word to `PREFIXES` globally**, test it mid-string against realistic 3-token names, not just check for English-word collisions: Korean/Vietnamese given names put a short syllable in the middle slot (`Park In Hwan`, `Nguyen To Nga`), and Western names put a bare initial there (`John V. Smith`). A word that looks safe ("nobody is named 'to'") can still swallow a real middle name/initial into the last name once it's a global prefix — confirmed regressions for `to`/`in`/`an`/`ten`/`then` and bare `v` this way (PR #191).

**Adding a flag-gated post-parse transform** (reorder/adjust) — add a `Constants` boolean (default `False`), implement a `handle_*()` method, and call it in `post_process()` after `handle_firstnames()` and before `handle_capitalization()`, gated on the flag. Default-off keeps existing parses byte-for-byte unchanged. Two shipped examples: `patronymic_name_order` gates both `handle_east_slavic_patronymic_name_order()` (#85) and `handle_turkic_patronymic_name_order()` (#185) — one flag driving two independent handlers, added in the same `post_process()` slot; `middle_name_as_last` gates `handle_middle_name_as_last()` (#133), which folds `middle_list` into `last_list`.

**Validating a new parsing rule** — before implementing, simulate it in a throwaway script against `TEST_NAMES` (plus a few target-language examples) to catch regressions/false-positives early. E.g. this surfaced the `last_base` `do`/`st`/`mc` empties and the patronymic `"David Michael Abramovich"` false-reorder.

## Gotchas

**Titles permanently shadow first names — be conservative** — any word in `TITLES` is always consumed as a title and can never be parsed as a first name. `"Dean"` is the canonical example: it's a common academic title *and* a common given name, so it is intentionally absent from the default titles (see `docs/customize.rst` — users who need it add it via opt-in `Constants`). Before adding a word to `TITLES`, ask: "Could this plausibly be someone's given name in any culture?" If yes, don't add it globally; it belongs in caller-supplied `Constants` instead. This same caution applies to international honorifics — `Prince`, `Sheikh`, `Frau` are all first names in some contexts.

**`is_leading_title()` infers titles beyond the `TITLES` set, but only in leading position** — an unrecognized multi-letter word ending in a single trailing period (matched via the `period_abbreviation` regex, `{2,}` letters) is treated as a title when it appears before the first name is set, e.g. `"Major. Dona Smith"` → `title='Major.'`. It's distinct from `is_title()` and does not mutate `C.titles`, so the periodless form (`"Major"`) is unaffected elsewhere. The `{2,}` length requirement — not a separate initials check — is what excludes single-letter initials like `"J."` from being swallowed as titles; the same word after the first name is left as a middle name. (#109; see `docs/usage.rst` "Leading Period-Abbreviation Titles")

**Cyrillic suffix regexes need `re.I` even when the pattern is suffix-only** — a Latin title-cased word (`Ivanovich`) keeps its suffix lowercase, so `re.I` seemed skippable; but an irregular Cyrillic suffix can be nearly the whole word (`ильич`), so title-casing capitalizes into the suffix itself (`Ильич`). `east_slavic_patronymic_cyrillic` shipped without `re.I` on the Latin reasoning and silently failed on capitalized irregular forms — don't assume Latin's title-case safety transfers to Cyrillic. (#185)

**`suffix_not_acronyms` vs `is_an_initial` tension** — single-letter roman numeral suffixes (`i`, `v`) are in `suffix_not_acronyms` but also match the `is_an_initial` regex (single uppercase letter), so `is_suffix()` rejects them. Two separate code paths need context-aware workarounds: (1) suffix-comma detection uses `are_suffixes_after_comma()` which bypasses `is_suffix()` for `suffix_not_acronyms` members; (2) lastname-comma post-comma parsing uses `is_suffix_at_lastname_comma_end()` which only fires when `nxt is None` and `len(parts)==2` (no `parts[2]` suffix segment). See issues #136, #144.

**Expected-failure tests use `@pytest.mark.xfail`** — the conftest parametrized fixture breaks `@unittest.expectedFailure`; always use `@pytest.mark.xfail` instead.

**`lc()` strips leading and trailing periods** — `'M.D.'` → `'m.d'`, not `'md'` (interior periods are preserved). Exception keys in `capitalization_exceptions` are dot-free, so lookups must also try `.replace('.', '')`.

**`is_suffix()`'s period-stripping is asymmetric** — it does `lc(piece).replace('.', '')` (strips *all* periods) before checking `suffix_acronyms`, but only `lc(piece)` (leading/trailing only) before checking `suffix_not_acronyms`. Code that reimplements this check instead of calling `is_suffix()` must mirror both branches or it will misclassify acronym suffixes with internal-only periods (e.g. `"M.D"` with no trailing dot) — bit `parse_nicknames()`'s `handle_match()` in PR #189.

**`_join_first_name_prefix` guard must exclude trailing suffixes** — suffix tokens are still in `pieces` when the helper runs (suffix detection happens in the assignment loop, later). The `reserve_last` guard must count `if not self.is_suffix(p)` to avoid treating a trailing suffix like "Jr." as a last-name slot; otherwise `"abdul salam jr"` → `last='jr'`.

**Doctests** — docstring examples in `nameparser/*.py` run under `uv run pytest` (`--doctest-modules`; `testpaths` is `tests` + `nameparser` only). The `.rst` doctests in `docs/` (`usage.rst`, `customize.rst`) are **not** run by pytest or CI (CI does `sphinx-build -b html`, not `-b doctest`), so verify `.rst` examples manually: `python3 -c "import doctest; print(doctest.testfile('docs/usage.rst', module_relative=False, optionflags=doctest.NORMALIZE_WHITESPACE))"`. Note `customize.rst` has pre-existing failures under `-b doctest` (CONSTANTS state leaks across examples — no per-example reset like `tests/conftest.py` provides — plus non-deterministic `SetManager` repr).

`Constants` class attributes (e.g. `patronymic_name_order`, `middle_name_as_last`) document behavior with a bare string literal placed right after the assignment — Sphinx's attribute-docstring convention. That string never becomes a real `__doc__`, so `--doctest-modules` (which walks `__doc__` attributes) never sees any `.. doctest::` examples inside it — this let a stale example slip through CI once (`middle_name_as_last`, #133). `tests/test_config_attribute_docstrings.py` (#195) closes that gap: it parses `nameparser/config/__init__.py` with `ast` to recover those literals and runs any doctest examples through `doctest.DocTestParser`/`DocTestRunner` explicitly, so `pytest -q` now exercises them too. When adding or editing a `.. doctest::` example in a `Constants` attribute's bare-string docstring, this is the mechanism that actually runs it — don't assume `--doctest-modules` covers it.

**`initials_separator` is intra-group only** — it controls the joiner between consecutive initials *within* a name group (e.g. two middle names in `middle_list`). Spaces *between* groups come from `initials_format`. To fully concatenate initials you need both `initials_separator=""` and `initials_format="{first}{middle}{last}"`.

**`pr/NNN` local branches** track upstream PRs — don't commit to them by accident. Check `git branch --show-current` before starting work.

**Prefix-join uses value-based `list.index()`** in `join_on_conjunctions` — fragile when a token value repeats (e.g. a trailing title that's also a suffix acronym, or two `van`s); constrain such lookups to start at `i + 1`. See #100.

**Title vs suffix is purely positional** — a word matching `TITLES` at the front of a name becomes `title`; the same word matching `SUFFIX_ACRONYMS`/`SUFFIX_NOT_ACRONYMS` at the end becomes `suffix` (never both, regardless of the word's real-world meaning). External test sources (old issue gists, etc.) sometimes assert `suffix` for a leading professional abbreviation like `RA`/`PD`/`Dipl.-Ing.` — that's the source data being wrong, not a parser bug. Verify position before "fixing" it.

### Tests (`tests/`)

**Prefer behavior tests over constant-content tests** — don't assert on the literal contents/structure of config constants (e.g. `SUFFIX_ACRONYMS == SET_A | SET_B`, `'x' in SOME_SET`). Test observable parsing behavior instead (`HumanName(...)` output). Constant-content assertions just create a second place to update whenever the lists change.

A parse-behavior test can still be a disguised constant-content test if it only exercises one or two hardcoded entries from a large list (e.g. guarding a specific missing-comma typo in `SUFFIX_ACRONYMS`) — it documents that one instance without catching the same bug class elsewhere in the list. Prefer a test on the structural property itself, or skip a dedicated test for narrow, unrepeatable typo fixes.

**When adding a new aggregate property** (like `given_names` or `surnames`), always include a test for the empty path — a name that produces no value for that property — so the `or self.C.empty_attribute_default` guard is covered. The conftest dual-fixture then automatically exercises both `""` and `None` variants. Example: `HumanName("Williams")` for a given-names property (last-name-only string has no first or middle).

**`python_classes = ["*Tests", "*TestCase"]`** in `pyproject.toml` — suffix style (`FooTests`), NOT prefix (`TestFoo`); wrong style silently skips discovery.

Tests run under **pytest** (via `uv run pytest`) and are split one file per concern (`tests/test_titles.py`, `tests/test_suffixes.py`, etc.). `tests/base.py` holds `HumanNameTestBase` — a plain (non-`unittest`) base whose `m()` helper is a custom assert that prints the original name string on failure (plus thin `assert*` shims so the moved test bodies are unchanged). `tests/conftest.py` defines an autouse fixture that runs **every test twice** — once with `empty_attribute_default = ''` and once with `None` — so reported counts are doubled (e.g. 11 methods → 22 results); it also snapshots/restores the scalar `CONSTANTS` config around each test to keep tests order-independent. `TEST_NAMES` (in `tests/test_variations.py`) is a list of name strings permuted into comma-separated variants as a regression check. Tests that should fail use `@pytest.mark.xfail`. When adding a parsing case, add it to the relevant `tests/test_*.py` file and consider adding the base form to `TEST_NAMES`.
