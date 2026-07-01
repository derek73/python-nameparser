# Design: Detect suffixes inside parenthesis/quotes before nickname extraction

Addresses [issue #111](https://github.com/derek73/python-nameparser/issues/111).

## Problem

`parse_nicknames()` runs before any other name processing and unconditionally
extracts everything found inside parenthesis, double quotes, or single quotes
into `nickname_list`, stripping it from the working string. This means
suffix-like content that happens to be delimited — `(Ret)`, `(Jr.)` — is
misclassified as a nickname instead of a suffix.

Examples of current (wrong) behavior:

- `Andrew Perkins, Jr., Col. (Ret)` → nickname: `Ret` (should be suffix)
- `Lon (Jr.) Williams` → nickname: `Jr.` (should be suffix)
- `Andrew Perkins (MBA)` → nickname: `MBA` (should be suffix)

Examples of current (correct) behavior that must not regress:

- `JEFFREY (JD) BRICKEN` → nickname: `JD` (ambiguous — `JD` is both a
  common given-name nickname and a law degree acronym; existing behavior
  treats it as a nickname and that must be preserved)

## Background

`SUFFIX_ACRONYMS` currently contains ~530 entries bulk-imported from
Wikipedia's post-nominal letters list
([af5bdab](https://github.com/derek73/python-nameparser/commit/af5bdabc160fc15054b59e078c658ac80a3cb1ff),
fixing #93). Investigating this set for the current fix turned up two
findings that shape the design:

1. `(ret)` and `(vet)` are the *only two* entries in the entire set that
   carry literal parentheses — an artifact of how the Wikipedia source
   formatted retired/veteran military status, not a deliberate design
   choice for nickname disambiguation. They belong in `SUFFIX_NOT_ACRONYMS`
   as bare words (`ret`, `vet`), consistent with how `jr`/`sr` are stored.
2. Of the remaining ~528 acronym entries, only **`ed`** and **`jd`**
   plausibly collide with common English given-name nicknames (Ed, JD).
   The rest (`mba`, `cpa`, `phd`, `rn`, etc.) are unambiguous
   certifications/degrees/honors that are never used as nicknames.

Because only 2 of ~530 entries are genuinely ambiguous, and that
ambiguity check is only ever needed in one place (`parse_nicknames()`), we
add a single small constant for the exception rather than splitting
`SUFFIX_ACRONYMS` into two large parallel lists. `SUFFIX_ACRONYMS` itself
is untouched — same value, same mutability, no API change.

### Constant addition in `nameparser/config/suffixes.py`

```python
SUFFIX_NOT_ACRONYMS = set([
    'dr', 'esq', 'esquire', 'jr', 'jnr', 'junior', 'sr', 'snr',
    '2', 'i', 'ii', 'iii', 'iv', 'v',
    'ret', 'vet',   # moved from literal "(ret)"/"(vet)" entries
])

SUFFIX_ACRONYMS_AMBIGUOUS = set([
    'ed', 'jd',   # acronym suffixes that commonly collide with given names/nicknames
])

SUFFIX_ACRONYMS = set([
    # unchanged: the full ~530-entry list, including 'ed' and 'jd'
    ...
])
```

`SUFFIX_ACRONYMS_AMBIGUOUS` is a small, standalone exception list — not a
partition of `SUFFIX_ACRONYMS`, so there's no second large list to keep in
sync and nothing to derive. "Unambiguous acronym suffix" is expressed as
`piece in SUFFIX_ACRONYMS and piece not in SUFFIX_ACRONYMS_AMBIGUOUS`
wherever it's needed, rather than as its own stored constant.

### Where to add a new suffix: a decision guide

1. **Is it a plain word/phrase, not an acronym** — e.g. `Junior`, `Senior`,
   `Doctor`-style abbreviations, roman numerals? → `SUFFIX_NOT_ACRONYMS`.
   Unchanged by this design.
2. **Is it an acronym/initialism** (e.g. all-caps letters like `MBA`,
   `PHD`, `JD`)? Add it to `SUFFIX_ACRONYMS` as always. Then ask: **could
   this exact letter sequence plausibly be someone's given name or common
   nickname on its own**, independent of context?
   - **No** (e.g. `MBA`, `CPA`, `RN`, `PHD` — nobody is named "Mba") →
     nothing further to do; it's already unambiguous by omission from
     `SUFFIX_ACRONYMS_AMBIGUOUS`.
   - **Yes** (e.g. `JD`, `ED` — both real given-name nicknames) → also add
     it to `SUFFIX_ACRONYMS_AMBIGUOUS`.

     This new list is read in exactly one place: the
     `HumanName.parse_nicknames()` method, and only for content found in
     parenthesis/quotes — it will *not* pull `JD`/`ED` out of parens as a
     suffix there; they stay nicknames, since that context is inherently
     ambiguous and nickname is the safer/more common reading (per the
     `JEFFREY (JD) BRICKEN` example).

     The `HumanName.is_suffix()` method never reads
     `SUFFIX_ACRONYMS_AMBIGUOUS` at all, before or after this design — it
     only checks `SUFFIX_ACRONYMS` (unchanged) and `SUFFIX_NOT_ACRONYMS`.
     So `is_suffix('JD')` keeps returning `True` outside of parens/quotes
     (e.g. after a comma: `"Doe, JD"`) exactly as it did before this
     design existed.

This guidance should go as a short comment above `SUFFIX_ACRONYMS_AMBIGUOUS`
in `nameparser/config/suffixes.py` when implemented, so future contributors
adding a suffix know when (rarely) they need to touch this second list.

### Config wiring in `nameparser/config/__init__.py`

Add one new customizable attribute, following the plain `SetManager` pattern
used by `first_name_titles`, `conjunctions`, and `first_name_prefixes`
(declared as a bare `SetManager`-typed attribute, assigned directly in
`__init__` — constructor param → `SetManager`, no descriptor):

- `suffix_acronyms_ambiguous: Iterable[str] = SUFFIX_ACRONYMS_AMBIGUOUS`
  constructor param, assigned as `self.suffix_acronyms_ambiguous =
  SetManager(suffix_acronyms_ambiguous)`, exposed as
  `self.C.suffix_acronyms_ambiguous`.

This deliberately does **not** use the `_CachedUnionMember` descriptor that
`prefixes`/`suffix_acronyms`/`suffix_not_acronyms`/`titles` use. That
descriptor is scoped specifically to the four sets whose union is cached in
`_pst` (`suffixes_prefixes_titles`) for prefix/suffix/title classification
elsewhere in the parser, and exists only to invalidate that cache when one of
those four is mutated. `suffix_acronyms_ambiguous` is a subtractive exception
list consulted in exactly one place, `parse_nicknames()` — it is not part of
that classification union and has no cache to invalidate. Giving it the
`_CachedUnionMember` descriptor would be needless machinery and would
silently fold it into `_pst`, which is misleading even though harmless today
(it's always a subset of `suffix_acronyms`).

`suffix_acronyms` itself is **unchanged**: still an independently-settable
`_CachedUnionMember`, same constructor param, same default. No breaking
change. A caller who customizes `suffix_acronyms` directly (adding their
own acronym suffixes) without also touching `suffix_acronyms_ambiguous`
simply gets the default (small, English-specific) ambiguity exceptions —
a reasonable default, easily overridden if they hit a collision in their
own custom acronyms.

## Approach

Modify `parse_nicknames()` in `nameparser/parser.py` to inspect each
regex match before deciding whether to route it to `nickname_list` or leave
it in `_full_name` for normal suffix processing downstream.

A match is **not** extracted as a nickname (left in `_full_name` for normal
downstream processing) if any of the following hold. In this case the
delimiters (`()`, `""`, or `''`) must **not** be reinserted — only the bare
inner content goes back into `_full_name`. Downstream tokenization only
strips spaces/commas (`parse_pieces`) and periods (`is_suffix`/`lc`); it does
not strip parens or quotes. Reinserting `m.group(0)` (e.g. literal `(Ret)`)
would leave `lc('(Ret)') == '(ret)'`, which never matches `suffix_not_acronyms`
(`'ret'`) or anything else, so the content would silently fail to be
recognized as a suffix downstream and would instead be absorbed as an
unrecognized word. So the content must go back in *undelimited* — e.g.
`Ret`, `Jr.`, `MBA` — so it reads exactly like it would have if the source
string never had parens/quotes around it, letting normal suffix/title/word
parsing handle it the same way it handles unparenthesized occurrences of the
same words:

1. The **inner content** (e.g. `Jr.`, `Ret`, `MBA`, without delimiters),
   lowercased/period-stripped via the existing `lc()` normalizer, is a
   member of `self.C.suffix_not_acronyms`, or is in `self.C.suffix_acronyms`
   but *not* in `self.C.suffix_acronyms_ambiguous`. Together these cover
   unambiguous post-nominal words (`jr`, `sr`, `ret`, `vet`, etc.) and
   unambiguous acronym suffixes (`mba`, `cpa`, `phd`, etc.) — deliberately
   excluding the 2-entry ambiguous set (`ed`, `jd`), which stay eligible to
   be treated as nicknames.
2. The **inner content ends in a period** (e.g. `Mgr.`, `Assoc.`). Real
   nicknames don't end in a period; content shaped like an abbreviation is
   more likely a suffix/title fragment that isn't in our suffix lists at
   all. This is a heuristic, not a suffix-list lookup — when it fires, the
   match is left in `_full_name` and flows into normal word-by-word parsing
   (it does not get force-classified as a suffix; it may end up as an
   unrecognized middle/last piece, or as a suffix if normal parsing
   separately identifies it as one).

`JD` has no trailing period and is in `SUFFIX_ACRONYMS_AMBIGUOUS`, so
neither rule fires for it — it stays a nickname, preserving current
behavior. A period-bearing form like `(J.D.)` would fall under rule 2 and
be excluded from nicknames; this is an accepted, deliberate trade-off.

### Implementation sketch

Replace the current bulk extraction:

```python
for _re in (re_quoted_word, re_double_quotes, re_parenthesis):
    if _re.search(self._full_name):
        self.nickname_list += [x for x in _re.findall(self._full_name)]
        self._full_name = _re.sub('', self._full_name)
```

with a per-match callback so each match can be individually routed:

```python
for _re in (re_quoted_word, re_double_quotes, re_parenthesis):
    def handle_match(m):
        content = m.group(1)
        stripped = lc(content)
        if (stripped in self.C.suffix_not_acronyms
                or (stripped in self.C.suffix_acronyms
                    and stripped not in self.C.suffix_acronyms_ambiguous)
                or content.endswith('.')):
            # Leave the bare content (no delimiters) so downstream
            # word-splitting/suffix-matching sees it exactly as if it
            # had never been wrapped in parens/quotes. Returning the
            # delimited m.group(0) instead would leave literal "(Ret)"
            # in _full_name, and is_suffix()/lc() only strip periods,
            # not parens/quotes, so it would never match suffix_not_acronyms.
            return content
        self.nickname_list.append(content)
        return ''
    self._full_name = _re.sub(handle_match, self._full_name)
```

This applies uniformly to all three delimiter regexes. In practice the
suffix checks only ever fire for the parenthesis regex today, since quoted
forms of these suffix words are uncommon in the test corpus — but the
logic is delimiter-agnostic and will correctly handle a quoted suffix if
one appears.

Note this changes surrounding whitespace behavior slightly versus the old
bulk `_re.sub('', ...)`: since the delimiters are dropped but the content is
kept in place, `"Col. (Ret)"` becomes `"Col. Ret"` (single space preserved,
same as if `"Ret"` had simply followed `"Col."` in the original string) —
consistent with the goal of making the content parse exactly like an
unparenthesized occurrence would.

## Scope boundaries

- `SUFFIX_ACRONYMS` and the `suffix_acronyms` config attribute are
  completely unchanged — same value, same mutability, no API break.
- Only one new constant/attribute pair is introduced:
  `SUFFIX_ACRONYMS_AMBIGUOUS` / `suffix_acronyms_ambiguous`.
- No changes to `is_suffix()`.
- Does not address #110 (additional apostrophe delimiters) or #112 (dynamic
  regex registration) — those are separate, out of scope here.
- Does not attempt to resolve the `ed`/`jd`-style ambiguity between suffix
  acronyms and nicknames; existing behavior (treat as nickname) is
  preserved by design via `SUFFIX_ACRONYMS_AMBIGUOUS`.
- Does not change `parse_full_name`'s suffix detection. That detection only
  recognizes a *trailing run* of suffix-shaped pieces in the no-comma parse
  path (`self.are_suffixes(pieces[i+1:])`); a comma segment is treated as a
  suffix unconditionally regardless of internal position. This means a
  suffix-shaped word freed from parens/quotes by this fix lands in
  `suffix_list` only when it's already in a trailing/comma position in the
  source string — e.g. `Andrew Perkins (MBA)` → suffix `MBA`, and
  `Andrew Perkins, Jr., Col. (Ret)` → suffix contains `Ret` (comma segment).
  But `Lon (Jr.) Williams` and `Col. (Ret.) Smith` have the suffix-shaped
  word in the *middle* of a no-comma name, with non-suffix pieces after it
  (`Williams`, `Smith`) — that trailing-run algorithm doesn't pull it into
  `suffix_list`, so it lands in `middle`/`first` instead, identically to how
  the bare (unparenthesized) string `"Lon Jr. Williams"` already parses on
  current `master`. This fix's actual guarantee is: **the delimited and
  undelimited forms of the same string now parse identically** — it no
  longer promises the freed word always becomes a suffix regardless of
  position. Verified against `master` before writing this note:
  `HumanName("Lon Jr. Williams")` → `middle == "Jr."`, and
  `HumanName("Col. Ret. Smith")` → `title == "Col."`, `first == "Ret."` —
  both already true without this fix, confirming the limitation is
  pre-existing in `parse_full_name` and not introduced here.

## Test cases to add

All in the existing nickname/suffix test modules:

| Input | Expected suffix | Expected nickname | Notes |
|---|---|---|---|
| `Andrew Perkins, Jr., Col. (Ret)` | contains `Ret` | empty | comma segment — trailing-run limitation doesn't apply |
| `Lon (Jr.) Williams` | empty | empty | mid-name, no comma — see "Scope boundaries"; parses identically to bare `"Lon Jr. Williams"` (`middle == "Jr."`) |
| `Col. (Ret.) Smith` | empty | empty | mid-name, no comma — same limitation; parses identically to bare `"Col. Ret. Smith"` (`title == "Col."`, `first == "Ret."`) |
| `Andrew Perkins (MBA)` | `MBA` | empty | trailing position |
| `JEFFREY (JD) BRICKEN` | empty | `JD` (regression guard) | |
| `Andrew Perkins (Mgr.)` | empty | empty (content flows into normal parsing, not force-classified either way) | |

Additionally, add API/behavior tests (not constant-content tests — those
just create a second place to update whenever the lists change):

- Customizing `suffix_acronyms_ambiguous` via `Constants()` changes
  parsing output: adding a custom entry there and parsing
  `"Andrew Perkins (XYZ)"` (where `XYZ` is also in `suffix_acronyms`)
  keeps `XYZ` classified as a nickname instead of a suffix.
- Removing `jd` from a custom `suffix_acronyms_ambiguous` and parsing
  `"Andrew Perkins (JD)"` (trailing position, so the freed word actually
  reaches `suffix_list` — see "Scope boundaries" for why a mid-name example
  like `JEFFREY (JD) BRICKEN` wouldn't work for this test) now routes `JD`
  to suffix instead of nickname (confirms the exception list, not a
  hardcoded check, drives the behavior).
