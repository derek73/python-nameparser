# Suffix-in-Parentheses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `parse_nicknames()` from misclassifying suffix-like content inside parentheses/quotes (e.g. `(Ret)`, `(Jr.)`, `(MBA)`) as nicknames, while preserving the existing `JEFFREY (JD) BRICKEN` → nickname `JD` behavior, per [issue #111](https://github.com/derek73/python-nameparser/issues/111).

**Architecture:** Add a small `SUFFIX_ACRONYMS_AMBIGUOUS` exception set (`ed`, `jd`) alongside the existing `SUFFIX_ACRONYMS`/`SUFFIX_NOT_ACRONYMS` constants, wire it into `Constants` as a plain `SetManager` attribute, and change `parse_nicknames()` from an unconditional bulk extraction into a per-match callback that leaves suffix-shaped content (or content ending in a period) in `_full_name` — undelimited — instead of routing it to `nickname_list`.

**Tech Stack:** Python, pytest (existing `HumanNameTestBase` fixture in `tests/base.py`).

**Spec:** [docs/superpowers/specs/2026-06-30-suffix-in-parens-design.md](../specs/2026-06-30-suffix-in-parens-design.md)

---

## File Structure

- `nameparser/config/suffixes.py` — move `'(ret)'`/`'(vet)'` out of `SUFFIX_ACRONYMS` into `SUFFIX_NOT_ACRONYMS` as bare `'ret'`/`'vet'`; add new `SUFFIX_ACRONYMS_AMBIGUOUS` constant with a decision-guide comment.
- `nameparser/config/__init__.py` — import the new constant; add `suffix_acronyms_ambiguous` as a plain `SetManager`-typed attribute (same pattern as `first_name_titles`/`conjunctions`/`first_name_prefixes`), constructor param, docstring entry.
- `nameparser/parser.py` — rewrite `HumanName.parse_nicknames()` (currently lines 774–793) to use a per-match callback instead of bulk `findall`/`sub`.
- `tests/test_suffixes.py` — add a config-plumbing test for `suffix_acronyms_ambiguous`, plus suffix-in-parens/quotes regression tests.
- `tests/test_nicknames.py` — add the `JD` regression-guard test and the ambiguous-content-stays-a-nickname tests.

No new files. No public API is removed or changed; `suffix_acronyms`/`SUFFIX_ACRONYMS` are untouched.

---

## Task 1: Add `SUFFIX_ACRONYMS_AMBIGUOUS` and wire `suffix_acronyms_ambiguous` into `Constants`

**Files:**
- Modify: `nameparser/config/suffixes.py`
- Modify: `nameparser/config/__init__.py`
- Test: `tests/test_suffixes.py`

This task only adds plumbing (a new constant + a new customizable `Constants` attribute). It does not change parsing behavior yet — `parse_nicknames()` doesn't read it until Task 2. The test here checks the customization API works, not the literal contents of the default set (that's covered end-to-end in Task 2 once the attribute actually affects parsing).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_suffixes.py`, inside `SuffixesTestCase`:

```python
    def test_suffix_acronyms_ambiguous_is_customizable(self) -> None:
        from nameparser.config import Constants
        custom = Constants(suffix_acronyms_ambiguous=['xyz'])
        self.assertEqual(set(custom.suffix_acronyms_ambiguous), {'xyz'})
        # Constructing without the kwarg still works and uses the module default.
        default = Constants()
        self.assertIn('jd', default.suffix_acronyms_ambiguous)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_acronyms_ambiguous_is_customizable -v`
Expected: FAIL with `TypeError: Constants.__init__() got an unexpected keyword argument 'suffix_acronyms_ambiguous'`

- [ ] **Step 3: Add the constant to `nameparser/config/suffixes.py`**

Remove these two lines from `SUFFIX_ACRONYMS` (currently lines 24–25):

```python
    '(ret)',
    '(vet)',
```

Add `'ret'` and `'vet'` to `SUFFIX_NOT_ACRONYMS` (currently lines 1–16), and append the new constant after `SUFFIX_ACRONYMS`'s closing docstring. The full top of the file becomes:

```python
SUFFIX_NOT_ACRONYMS = set([
    'dr',
    'esq',
    'esquire',
    'jr',
    'jnr',
    'junior',
    'sr',
    'snr',
    '2',
    'i',
    'ii',
    'iii',
    'iv',
    'v',
    'ret',
    'vet',
])
"""

Post-nominal pieces that are not acronyms. The parser does not remove periods
when matching against these pieces.

"""
SUFFIX_ACRONYMS = set([
    '8-vsb',
    'aas',
    ...
```

(Leave every other entry in `SUFFIX_ACRONYMS` untouched — only the two literal-parenthesis entries move. Everything from `'8-vsb'` onward through the closing `])` stays exactly as-is, just re-indexed by the two removed lines.)

Append this after the `SUFFIX_ACRONYMS` closing docstring (the `"""..."""` block that currently ends the file):

```python
SUFFIX_ACRONYMS_AMBIGUOUS = set([
    # Suffix acronyms that also commonly work as given-name nicknames on
    # their own (e.g. "Ed", "JD"). Read only by HumanName.parse_nicknames()
    # when deciding whether parenthesized/quoted content is a nickname or a
    # suffix — content matching one of these stays a nickname rather than
    # being reclassified as a suffix, since that's the more common reading
    # in ambiguous, delimiter-only context.
    #
    # When adding a new entry to SUFFIX_ACRONYMS, also add it here only if
    # the exact letter sequence could plausibly be someone's given name or
    # common nickname on its own (e.g. 'jd', 'ed'). Unambiguous
    # certifications/degrees (e.g. 'mba', 'cpa', 'phd') don't need an entry.
    'ed',
    'jd',
])
"""

Acronym suffixes from SUFFIX_ACRONYMS that also plausibly collide with a
common given-name nickname. Not a partition of SUFFIX_ACRONYMS — a small,
standalone exception list consulted only by parse_nicknames().

"""
```

- [ ] **Step 4: Wire it into `Constants` in `nameparser/config/__init__.py`**

Add the import near the existing suffix imports (after line 44):

```python
from nameparser.config.suffixes import SUFFIX_ACRONYMS
from nameparser.config.suffixes import SUFFIX_NOT_ACRONYMS
from nameparser.config.suffixes import SUFFIX_ACRONYMS_AMBIGUOUS
```

Add a plain `SetManager`-typed class attribute next to `first_name_titles`/`conjunctions`/`first_name_prefixes` (currently lines 257–259) — **not** a `_CachedUnionMember`, since this set isn't part of the `_pst` prefix/suffix/title union and needs no cache invalidation:

```python
    first_name_titles: SetManager
    conjunctions: SetManager
    first_name_prefixes: SetManager
    suffix_acronyms_ambiguous: SetManager
```

Add the constructor param (next to `suffix_not_acronyms`, currently line 390) and its docstring entry (next to the `suffix_not_acronyms` doc entry, currently lines 239–240):

```python
    :param set suffix_acronyms_ambiguous:
        :py:attr:`~suffixes.SUFFIX_ACRONYMS_AMBIGUOUS` wrapped with :py:class:`SetManager`.
```

```python
    def __init__(self,
                 prefixes: Iterable[str] = PREFIXES,
                 suffix_acronyms: Iterable[str] = SUFFIX_ACRONYMS,
                 suffix_not_acronyms: Iterable[str] = SUFFIX_NOT_ACRONYMS,
                 suffix_acronyms_ambiguous: Iterable[str] = SUFFIX_ACRONYMS_AMBIGUOUS,
                 titles: Iterable[str] = TITLES,
                 ...
```

And assign it directly in the body (next to the other four descriptor assignments, currently lines 402–408 — this one is a plain attribute assignment, not a descriptor, so it doesn't need to come before any `suffixes_prefixes_titles` read):

```python
        self.prefixes = SetManager(prefixes)
        self.suffix_acronyms = SetManager(suffix_acronyms)
        self.suffix_not_acronyms = SetManager(suffix_not_acronyms)
        self.titles = SetManager(titles)
        self.first_name_titles = SetManager(first_name_titles)
        self.conjunctions = SetManager(conjunctions)
        self.first_name_prefixes = SetManager(first_name_prefixes)
        self.suffix_acronyms_ambiguous = SetManager(suffix_acronyms_ambiguous)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_suffixes.py::SuffixesTestCase::test_suffix_acronyms_ambiguous_is_customizable -v`
Expected: PASS

- [ ] **Step 6: Run the full suite to check nothing else broke from moving `(ret)`/`(vet)`**

Run: `pytest -q`
Expected: all pass (no test currently exercises `'(ret)'`/`'(vet)'`, or bare `'ret'`/`'vet'` as suffixes, per the check done during planning — `grep -rn "Ret\b\|Vet\b" tests/*.py` returns nothing)

- [ ] **Step 7: Commit**

```bash
git add nameparser/config/suffixes.py nameparser/config/__init__.py tests/test_suffixes.py
git commit -m "config: add SUFFIX_ACRONYMS_AMBIGUOUS, move (ret)/(vet) to SUFFIX_NOT_ACRONYMS"
```

---

## Task 2: Rewrite `parse_nicknames()` to route suffix-shaped content out of `nickname_list`

**Files:**
- Modify: `nameparser/parser.py:774-793` (`HumanName.parse_nicknames`)
- Test: `tests/test_nicknames.py`, `tests/test_suffixes.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_suffixes.py`, inside `SuffixesTestCase` (these are the spec's test-table rows for content that should stop being nicknames and start being suffixes):

```python
    def test_suffix_in_parenthesis_with_other_suffixes(self) -> None:
        hn = HumanName("Andrew Perkins, Jr., Col. (Ret)")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.assertIn("Ret", hn.suffix)
        self.m(hn.nickname, "", hn)

    def test_suffix_in_parenthesis_mid_name(self) -> None:
        # "Jr." is suffix-shaped, so parse_nicknames() no longer treats it as
        # a nickname. But it isn't in trailing position, and parse_full_name's
        # suffix detection only recognizes a trailing run of suffix-shaped
        # pieces -- so it lands wherever normal parsing would put a bare
        # mid-name "Jr." token, exactly as if the parens were never there
        # (verified: HumanName("Lon Jr. Williams") parses identically).
        # Known limitation: making this land in `suffix` would require
        # changing parse_full_name's suffix detection, out of scope here --
        # issue #111 is specifically about the nickname misclassification.
        hn = HumanName("Lon (Jr.) Williams")
        self.m(hn.first, "Lon", hn)
        self.m(hn.middle, "Jr.", hn)
        self.m(hn.last, "Williams", hn)
        self.m(hn.suffix, "", hn)
        self.m(hn.nickname, "", hn)

    def test_suffix_in_parenthesis_with_period(self) -> None:
        # Same known limitation as above: "Ret." is mid-name (no comma), so
        # it's outside the trailing run parse_full_name's suffix detection
        # requires. It parses exactly as bare "Col. Ret. Smith" would.
        hn = HumanName("Col. (Ret.) Smith")
        self.m(hn.title, "Col.", hn)
        self.m(hn.first, "Ret.", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "", hn)
        self.m(hn.nickname, "", hn)

    def test_acronym_suffix_in_parenthesis(self) -> None:
        hn = HumanName("Andrew Perkins (MBA)")
        self.m(hn.first, "Andrew", hn)
        self.m(hn.last, "Perkins", hn)
        self.m(hn.suffix, "MBA", hn)
        self.m(hn.nickname, "", hn)

    def test_period_terminated_content_in_parenthesis_not_forced_either_way(self) -> None:
        # "Mgr." isn't in any suffix list, but it ends in a period, so the
        # period heuristic (rule 2) excludes it from nickname_list. It flows
        # into normal parsing instead of being force-classified as a suffix.
        hn = HumanName("Andrew Perkins (Mgr.)")
        self.m(hn.nickname, "", hn)
        self.m(hn.suffix, "", hn)

    def test_suffix_acronyms_ambiguous_custom_entry_stays_nickname(self) -> None:
        # A custom suffix_acronyms_ambiguous entry keeps a suffix_acronyms
        # member classified as a nickname instead of a suffix, confirming
        # the exception list -- not a hardcoded check -- drives the behavior.
        from nameparser.config import Constants
        C = Constants(
            suffix_acronyms=['xyz'],
            suffix_acronyms_ambiguous=['xyz'],
        )
        hn = HumanName("Andrew Perkins (XYZ)", constants=C)
        self.m(hn.nickname, "XYZ", hn)
        self.m(hn.suffix, "", hn)

    def test_suffix_acronyms_ambiguous_removal_routes_to_suffix(self) -> None:
        # Removing 'jd' from a custom suffix_acronyms_ambiguous flips JD
        # from nickname to suffix. Uses a trailing-position name (unlike the
        # JEFFREY (JD) BRICKEN regression guard) so parse_full_name's
        # trailing-run suffix detection actually picks it up -- see the
        # known mid-name limitation noted on the tests above.
        from nameparser.config import Constants
        C = Constants(suffix_acronyms_ambiguous=[])
        hn = HumanName("Andrew Perkins (JD)", constants=C)
        self.m(hn.nickname, "", hn)
        self.m(hn.suffix, "JD", hn)
```

Add to `tests/test_nicknames.py`, inside `NicknameTestCase` (regression guard for the ambiguous case that must NOT change):

```python
    def test_ambiguous_suffix_acronym_in_parenthesis_stays_nickname(self) -> None:
        # JD is in SUFFIX_ACRONYMS_AMBIGUOUS: both a law-degree acronym and a
        # common given-name nickname. Existing behavior (nickname) must be
        # preserved -- see issue #111.
        hn = HumanName("JEFFREY (JD) BRICKEN")
        self.m(hn.nickname, "JD", hn)
        self.m(hn.suffix, "", hn)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_suffixes.py tests/test_nicknames.py -v -k "suffix_in_parenthesis or acronym_suffix_in_parenthesis or period_terminated_content or suffix_acronyms_ambiguous or ambiguous_suffix_acronym"`
Expected: FAIL — e.g. `test_suffix_in_parenthesis_with_other_suffixes` fails because `hn.suffix` is empty and `hn.nickname` is `"Ret"` under current behavior. The two `suffix_acronyms_ambiguous` customization tests fail with `TypeError: Constants.__init__() got an unexpected keyword argument` if Task 1 wasn't done, or with wrong nickname/suffix values if Task 1 is done but this task isn't.

- [ ] **Step 3: Rewrite `parse_nicknames()` in `nameparser/parser.py`**

Replace the current method body (lines 774–793):

```python
    def parse_nicknames(self) -> None:
        """
        The content of parenthesis or quotes in the name will be added to the
        nicknames list. This happens before any other processing of the name.

        Single quotes cannot span white space characters and must border
        white space to allow for quotes in names like O'Connor and Kawai'ae'a.
        Double quotes and parenthesis can span white space.

        Loops through 3 :py:data:`~nameparser.config.regexes.REGEXES`;
        `quoted_word`, `double_quotes` and `parenthesis`.
        """

        re_quoted_word = self.C.regexes.quoted_word
        re_double_quotes = self.C.regexes.double_quotes
        re_parenthesis = self.C.regexes.parenthesis

        for _re in (re_quoted_word, re_double_quotes, re_parenthesis):
            if _re.search(self._full_name):
                self.nickname_list += [x for x in _re.findall(self._full_name)]
                self._full_name = _re.sub('', self._full_name)
```

with:

```python
    def parse_nicknames(self) -> None:
        """
        The content of parenthesis or quotes in the name will be added to the
        nicknames list, unless that content is suffix-shaped -- an unambiguous
        suffix_not_acronyms/suffix_acronyms member, or content ending in a
        period -- in which case it's left in place (undelimited) for normal
        downstream suffix/title/word parsing instead. This happens before any
        other processing of the name.

        Single quotes cannot span white space characters and must border
        white space to allow for quotes in names like O'Connor and Kawai'ae'a.
        Double quotes and parenthesis can span white space.

        Loops through 3 :py:data:`~nameparser.config.regexes.REGEXES`;
        `quoted_word`, `double_quotes` and `parenthesis`.
        """

        re_quoted_word = self.C.regexes.quoted_word
        re_double_quotes = self.C.regexes.double_quotes
        re_parenthesis = self.C.regexes.parenthesis

        def handle_match(m: 're.Match[str]') -> str:
            content = m.group(1)
            stripped = lc(content)
            is_unambiguous_suffix = (
                stripped in self.C.suffix_not_acronyms
                or (stripped in self.C.suffix_acronyms
                    and stripped not in self.C.suffix_acronyms_ambiguous)
            )
            if is_unambiguous_suffix or content.endswith('.'):
                # Leave the bare content -- no delimiters -- so downstream
                # word-splitting/suffix-matching sees it exactly as if it had
                # never been wrapped in parens/quotes. is_suffix()/lc() only
                # strip periods, never parens/quotes, so returning m.group(0)
                # here (e.g. literal "(Ret)") would never match
                # suffix_not_acronyms ("ret").
                return content
            self.nickname_list.append(content)
            return ''

        for _re in (re_quoted_word, re_double_quotes, re_parenthesis):
            self._full_name = _re.sub(handle_match, self._full_name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_suffixes.py tests/test_nicknames.py -v`
Expected: PASS for all new tests

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: all pass, including the pre-existing nickname tests (`test_nickname_in_parenthesis`, `test_two_word_nickname_in_parenthesis`, `test_parenthesis_are_removed_from_name`, `test_duplicate_parenthesis_are_removed_from_name`, etc. — none of their parenthesized content is suffix-shaped or period-terminated, so they're unaffected)

- [ ] **Step 6: Commit**

```bash
git add nameparser/parser.py tests/test_suffixes.py tests/test_nicknames.py
git commit -m "fix: don't extract suffix-shaped parenthesized/quoted content as nicknames (#111)"
```

---

## Self-Review Notes

- **Spec coverage:** Constants/config changes (spec §"Constant addition", §"Config wiring") → Task 1. Parser rewrite and both design rules (§"Approach", rules 1–2) → Task 2 Step 3. All six spec test-table rows → Task 2 Step 1. Both customization behavior tests from spec §"Test cases to add" → Task 2 Step 1. Scope boundaries (no `is_suffix()` change, `SUFFIX_ACRONYMS`/`suffix_acronyms` untouched) → satisfied by construction; nothing in either task touches `is_suffix()` or removes/renames anything from `SUFFIX_ACRONYMS`.
- **No placeholders:** every step shows full code, exact commands, and expected output.
- **Type/name consistency:** `suffix_acronyms_ambiguous` (constructor param, attribute, config docstring) and `SUFFIX_ACRONYMS_AMBIGUOUS` (module constant) are spelled identically across both tasks. `handle_match`/`is_unambiguous_suffix` names introduced in Task 2 aren't referenced elsewhere, so no cross-task drift risk.
