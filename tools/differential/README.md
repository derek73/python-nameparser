# Differential harness (v1 vs 2.0)

Dev-only tooling for the 2.0 migration (migration plan S5). Not
shipped (excluded from the wheel by the packaging config -- only
`nameparser/` is packaged) and not CI-gated. Run it by hand when
touching parsing behavior, and before cutting a 2.0 release.

Two processes, two environments:

- `worker_v1.py` runs under a **pinned nameparser 1.4** installed fresh
  from PyPI via a PEP 723 inline script. It must be invoked with
  `uv run --no-project` -- **without `--no-project`, `uv` installs the
  working tree as an editable dependency and the 1.4 pin never takes
  effect**, silently comparing 2.0 against itself.
- `compare.py` runs in the project's own dev environment and imports
  `nameparser` normally (the 2.0 facade, which still speaks the v1
  component names).

## Running it

```
uv run python tools/differential/build_corpus.py --ref <ref> > tools/differential/corpus.jsonl   # only when regenerating
uv run python tools/differential/compare.py
```

`compare.py` spawns the worker as a subprocess, feeds it every corpus
name as a line of JSON, and diffs the two component dicts on the seven
v1 field names (`title`, `first`, `middle`, `last`, `suffix`,
`nickname`, `maiden` -- both sides use these keys, so no field mapping
is needed). Every diff is checked against `expected_changes.toml`:

- Matches a rule -> counted as an intentional, classified change.
- Matches no rule -> printed under `UNEXPLAINED` and the run exits 1.

An unexplained diff means either a real 2.0 parity bug (fix it, don't
allowlist it) or a known change whose `expected_changes.toml` rule
needs widening. The run must exit 0 before a 2.0 release; the classified
summary it prints is the source for the "Behavior Changes" section of
`docs/release_log.rst`.

## The two corpora

`compare.py` reads **every** `corpus*.jsonl` beside it by default
(deduped), because a corpus you have to ask for by name is a corpus
that stops being run. Pass `--corpus PATH` (repeatable) to narrow it.

| File | Source | Blind to |
|---|---|---|
| `corpus.jsonl` | v1's own test suite at a pinned ref | anything 2.0 added — v1's authors had no reason to test a typographic nickname delimiter or a Cyrillic title |
| `corpus_issues.jsonl` | name-like strings harvested from the GitHub issue tracker | anything nobody ever reported |

They are deliberately separate rather than merged: `corpus.jsonl` is
reproducible forever from an immutable git ref, while the issue
tracker is mutable, so regenerating the second one is an explicit,
reviewable act that can only add names.

The issue corpus earned its place on the first run — 166 of its 198
names were not in `corpus.jsonl`, and it immediately surfaced five
intended-but-unclassified 2.0 behaviors (#273 typographic delimiters,
#269 non-Latin vocabulary) plus one shape no test had considered: a
**leading** `"Ph. D."`, which v1 split into title `Ph.` + given `D.`.

## Corpus provenance

`corpus.jsonl` is checked in as a test fixture. It was built by
`build_corpus.py`'s AST walk over every top-level `tests/test_*.py`
file (the v1-style test banks; `tests/v2/` is a separate 2.0-only
harness and is deliberately not scanned), reading each file via
`git show <ref>:<path>` rather than the working tree:

```
uv run python tools/differential/build_corpus.py --ref 2d5d8c2 > tools/differential/corpus.jsonl
```

`2d5d8c2` ("Trim constant-factor waste on the tokenize hot path") is
the last commit before M12 reconciled/edited the v1 test banks against
the 2.0 facade -- M12 changed some expectations in place and deleted
bucket-A tests outright, which would have shrunk and skewed the
corpus. Reading history at an old ref via `git show` is a read-only
operation on this worktree's own log; it does not check out, stash, or
otherwise mutate anything.

The AST extraction over-collects on purpose (string literals passed as
`HumanName(...)`'s first argument, plus string members of module-level
list/dict/tuple banks that contain a space) -- more candidate strings
is more coverage, and the corpus is deduplicated. Obvious non-names
(strings containing `{`, `@`, or a backslash -- format placeholders,
decorator/email-shaped fixtures, escape sequences) are dropped.

Regenerate the corpus only if the v1 test banks are revisited again at
a still-earlier point in history; otherwise leave the checked-in file
alone so the harness stays comparable run to run.

`corpus_issues.jsonl` is built by `build_issues_corpus.py` from the
issue tracker (`gh issue list --state all`), taking `HumanName("...")`
calls and quoted capitalized phrases -- the two ways a reporter writes
the input that broke on them. Regenerate with:

```
uv run python tools/differential/build_issues_corpus.py > tools/differential/corpus_issues.jsonl
```

Unlike the ref-pinned corpus this is a mutable source, so the
checked-in file is the snapshot under test; re-running only adds names
as new issues arrive. Over-collection is fine in both builders: the
comparator just parses more names, and junk like `Bridge (1.4)` costs
one parse and produces no diff.

## `expected_changes.toml`

Each `[[change]]` entry needs `issue` (a short label, ideally an
issue number or `fix(<slug>)` matching a `tests/v2/cases.py`
classification) and may narrow its match with `name_regex` (searched
against the raw input string) and/or `fields` (the diffing rule
matches only if the observed diff fields are a subset of this list).
Keep both as tight as the actual diff allows -- a loose rule can mask
a real regression.

Some entries in the seed list are for behavior families that this
particular corpus (pre-M12 v1 test strings) happens not to contain any
example of (e.g. custom suffix-delimiter rendering, which only fires
under a non-default `Policy`). They're kept in the file anyway,
matching the family documented in `tests/v2/cases.py`, so the rule is
ready the moment a matching string is added to the corpus.
